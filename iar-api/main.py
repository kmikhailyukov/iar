import os
import uuid
import json
import asyncio
import logging
from datetime import datetime
from typing import Optional, List

import psycopg2
import psycopg2.extras
import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="IAR API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL")
ZORROBPM_API = os.getenv("ZORROBPM_API", "https://bpm.zorro.kt")
LOTUS_MOCK_URL = os.getenv("LOTUS_MOCK_URL", "http://iar-lotus-mock:8000")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SEC", "30"))


# ── Mock LLM classifier (inline fallback, no BPM/RabbitMQ needed) ─────────────

DEPT_KEYWORDS = {
    "ДОЭ":    ["эффективност", "операционн", "оптимизац", "процесс", "kpi", "реинжиниринг", "затрат", "производительност"],
    "ДУКО":   ["клиент", "сервис", "опыт", "обращени", "nps", "жалоб", "удовлетвор", "поддержк", "качеств обслуж"],
    "ДПОТ":   ["проект", "трансформац", "цифровиз", "дорожная карта", "agile", "инициатив", "программ модерниз"],
    "УДЦТиЭ": ["цифров", "технолог", "инновац", "автоматиз", "систем", "it ", "платформ", "диджитал"],
}

DEPT_EMPLOYEES = {
    "ДОЭ":    {"id": "EMP_001", "name": "Менеджер ДОЭ",    "position": "Главный менеджер"},
    "ДУКО":   {"id": "EMP_002", "name": "Менеджер ДУКО",   "position": "Менеджер"},
    "ДПОТ":   {"id": "EMP_003", "name": "Менеджер ДПОТ",   "position": "Менеджер"},
    "УДЦТиЭ": {"id": "EMP_004", "name": "Менеджер УДЦТиЭ", "position": "Управляющий директор"},
}

DEPT_FUNCTIONS = {
    "ДОЭ":    "реинжиниринг бизнес-процессов, контроль KPI, оптимизация затрат, нормирование труда, операционный аудит",
    "ДУКО":   "обслуживание клиентов, управление NPS, обработка жалоб и обращений, клиентский сервис, удовлетворённость пользователей",
    "ДПОТ":   "управление проектами, цифровая трансформация, разработка дорожных карт, Agile/Scrum, стратегические инициативы",
    "УДЦТиЭ": "цифровые технологии, IT-платформы, автоматизация и роботизация процессов, технологические инновации, системная интеграция",
}

def run_mock_classify(text: str) -> dict:
    text_lower = text.lower()
    scores = {dept: sum(1 for kw in kws if kw in text_lower) for dept, kws in DEPT_KEYWORDS.items()}
    matched = {dept: [kw for kw in kws if kw in text_lower] for dept, kws in DEPT_KEYWORDS.items()}
    total = sum(scores.values())
    if total == 0:
        dept, confidence = "ДОЭ", 0.35
    else:
        dept = max(scores, key=scores.get)
        confidence = round(min(0.95, 0.45 + scores[dept] / total * 0.55), 3)
    zone = "GREEN" if confidence >= 0.8 else ("YELLOW" if confidence >= 0.5 else "RED")
    emp = DEPT_EMPLOYEES[dept]
    sorted_depts = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top3 = [{"department_code": d, "confidence": round(scores[d] / max(total, 1) * confidence, 2)} for d, _ in sorted_depts[:3]]

    kw_line = (
        f"Ключевые слова в тексте: {', '.join(matched[dept])}"
        if matched[dept] else "Явных ключевых слов не найдено (низкая уверенность)"
    )
    func_line = f"Функции {dept}: {DEPT_FUNCTIONS[dept]}"
    exec_line = f"Исполнитель: {emp['name']} ({emp['position']}), уверенность {round(confidence * 100)}%"

    return {
        "suggested_dept": dept,
        "suggested_executor": emp["id"],
        "executor_name": emp["name"],
        "confidence": confidence,
        "confidence_zone": zone,
        "justification": f"{kw_line}\n{func_line}\n{exec_line}",
        "top3_json": top3,
    }


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def db_fetchone(query: str, params=None):
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params or ())
            return cur.fetchone()
    finally:
        conn.close()


def db_fetchall(query: str, params=None):
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params or ())
            return cur.fetchall()
    finally:
        conn.close()


def db_execute(query: str, params=None):
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params or ())
            try:
                result = cur.fetchone()
            except Exception:
                result = None
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Pydantic models ───────────────────────────────────────────────────────────

class CreateAssignmentRequest(BaseModel):
    text: str
    author_id: str = "system"
    due_date: Optional[str] = None
    priority: str = "MEDIUM"
    lotus_id: Optional[str] = None


class ClassificationResult(BaseModel):
    suggested_dept: str
    suggested_executor: str
    confidence: float
    confidence_zone: str
    justification: str
    top3_json: list
    executor_name: Optional[str] = None


class ConfirmRequest(BaseModel):
    action: str  # ACCEPTED | CORRECTED | MANUAL
    assigned_to: Optional[str] = None
    assigned_dept: Optional[str] = None
    comment: Optional[str] = None
    assigned_by: Optional[str] = None


class DisputeRequest(BaseModel):
    disputed_dept: str
    comment: Optional[str] = None


# ── BPM helpers ───────────────────────────────────────────────────────────────

def bpm_start_process(assignment_id: str, text: str, priority: str) -> Optional[str]:
    """Start a ZorroBPM process instance and return its ID."""
    try:
        resp = httpx.post(
            f"{ZORROBPM_API}/process-instances",
            json={
                "processDefinitionKey": "iar-routing",
                "variables": [
                    {"name": "assignmentId", "value": str(assignment_id), "type": "STRING"},
                    {"name": "assignmentText", "value": text, "type": "STRING"},
                    {"name": "priority", "value": priority, "type": "STRING"},
                ],
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        # ZorroBPM may return id or processInstanceId
        return str(data.get("id") or data.get("processInstanceId") or "")
    except Exception as e:
        logger.error(f"BPM start process error: {e}")
        return None


def bpm_find_user_task(instance_id: str, task_name_contains: str) -> Optional[dict]:
    """Find an active user task for a given process instance."""
    try:
        resp = httpx.get(
            f"{ZORROBPM_API}/user-tasks",
            params={"processInstanceId": instance_id, "completed": "false"},
            timeout=10,
        )
        resp.raise_for_status()
        tasks = resp.json()
        if isinstance(tasks, list):
            for task in tasks:
                name = (task.get("name") or task.get("taskDefinitionKey") or "").lower()
                if task_name_contains.lower() in name:
                    return task
            # Return first task if no match
            if tasks:
                return tasks[0]
        elif isinstance(tasks, dict):
            items = tasks.get("items") or tasks.get("tasks") or []
            for task in items:
                name = (task.get("name") or task.get("taskDefinitionKey") or "").lower()
                if task_name_contains.lower() in name:
                    return task
            if items:
                return items[0]
    except Exception as e:
        logger.error(f"BPM find user task error: {e}")
    return None


def bpm_complete_user_task(task_id: str, variables: list) -> bool:
    """Complete a user task in ZorroBPM."""
    try:
        resp = httpx.post(
            f"{ZORROBPM_API}/user-tasks/{task_id}/complete",
            json={"variables": variables},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"BPM complete user task error: {e}")
        return False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/assignments")
def create_assignment(req: CreateAssignmentRequest):
    assignment_id = str(uuid.uuid4())
    due_date = None
    if req.due_date:
        try:
            due_date = datetime.fromisoformat(req.due_date)
        except Exception:
            due_date = None

    row = db_execute(
        """
        INSERT INTO assignments (id, text, author_id, due_date, priority, status, lotus_id)
        VALUES (%s, %s, %s, %s, %s, 'NEW', %s)
        RETURNING id, status, created_at
        """,
        (assignment_id, req.text, req.author_id, due_date, req.priority, req.lotus_id),
    )

    # Log creation
    db_execute(
        "INSERT INTO decision_log (assignment_id, actor_id, action, payload) VALUES (%s, %s, %s, %s)",
        (assignment_id, req.author_id, "CREATED", json.dumps({"text": req.text[:100]})),
    )

    # Run inline mock classification immediately (no BPM/RabbitMQ dependency)
    try:
        clf = run_mock_classify(req.text)
        db_execute(
            """
            UPDATE assignments SET
                suggested_dept = %s, suggested_executor = %s,
                confidence = %s, confidence_zone = %s,
                justification = %s, top3_json = %s,
                status = 'CLASSIFIED', updated_at = NOW()
            WHERE id = %s
            """,
            (clf["suggested_dept"], clf["suggested_executor"], clf["confidence"],
             clf["confidence_zone"], clf["justification"], json.dumps(clf["top3_json"]), assignment_id),
        )
        db_execute(
            "INSERT INTO decision_log (assignment_id, actor_id, action, payload) VALUES (%s, %s, %s, %s)",
            (assignment_id, "llm-inline", "CLASSIFIED",
             json.dumps({"dept": clf["suggested_dept"], "zone": clf["confidence_zone"]})),
        )
        logger.info(f"Inline classification: {assignment_id} → {clf['suggested_dept']} ({clf['confidence_zone']})")
    except Exception as e:
        logger.error(f"Inline classification error: {e}")

    # Try to start BPM process (optional, non-blocking)
    bpm_instance_id = bpm_start_process(assignment_id, req.text, req.priority)
    if bpm_instance_id:
        db_execute(
            "UPDATE assignments SET bpm_instance_id = %s, updated_at = NOW() WHERE id = %s",
            (bpm_instance_id, assignment_id),
        )
        logger.info(f"BPM instance started: {bpm_instance_id}")

    return {"id": assignment_id, "bpm_instance_id": bpm_instance_id, "status": "CLASSIFIED"}


@app.get("/api/v1/assignments")
def list_assignments(status: Optional[str] = None, limit: int = 50):
    if status:
        rows = db_fetchall(
            "SELECT * FROM assignments WHERE status = %s ORDER BY created_at DESC LIMIT %s",
            (status, limit),
        )
    else:
        rows = db_fetchall(
            "SELECT * FROM assignments ORDER BY created_at DESC LIMIT %s",
            (limit,),
        )
    return [dict(r) for r in rows]


@app.get("/api/v1/assignments/{assignment_id}")
def get_assignment(assignment_id: str):
    row = db_fetchone("SELECT * FROM assignments WHERE id = %s", (assignment_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return dict(row)


@app.post("/api/v1/assignments/{assignment_id}/classification")
def save_classification(assignment_id: str, result: ClassificationResult):
    row = db_fetchone("SELECT id FROM assignments WHERE id = %s", (assignment_id,))
    if not row:
        raise HTTPException(status_code=404, detail="Assignment not found")

    db_execute(
        """
        UPDATE assignments SET
            suggested_dept = %s,
            suggested_executor = %s,
            confidence = %s,
            confidence_zone = %s,
            justification = %s,
            top3_json = %s,
            status = 'CLASSIFIED',
            updated_at = NOW()
        WHERE id = %s
        """,
        (
            result.suggested_dept,
            result.suggested_executor,
            result.confidence,
            result.confidence_zone,
            result.justification,
            json.dumps(result.top3_json),
            assignment_id,
        ),
    )

    db_execute(
        "INSERT INTO decision_log (assignment_id, actor_id, action, payload) VALUES (%s, %s, %s, %s)",
        (
            assignment_id,
            "llm-worker",
            "CLASSIFIED",
            json.dumps({
                "dept": result.suggested_dept,
                "executor": result.suggested_executor,
                "confidence": result.confidence,
                "zone": result.confidence_zone,
            }),
        ),
    )

    logger.info(
        f"Classification saved for {assignment_id}: {result.suggested_dept} ({result.confidence_zone})"
    )
    return {"status": "ok"}


@app.post("/api/v1/assignments/{assignment_id}/confirm")
def confirm_assignment(assignment_id: str, req: ConfirmRequest):
    assignment = db_fetchone("SELECT * FROM assignments WHERE id = %s", (assignment_id,))
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # Determine final assignment targets
    if req.action == "ACCEPTED":
        assigned_to = assignment["suggested_executor"]
        assigned_dept = assignment["suggested_dept"]
    else:
        assigned_to = req.assigned_to or assignment["suggested_executor"]
        assigned_dept = req.assigned_dept or assignment["suggested_dept"]

    actor = req.assigned_by or assignment.get("assigned_by") or "manager1"

    db_execute(
        """
        UPDATE assignments SET
            assigned_to = %s,
            assigned_dept = %s,
            assignment_action = %s,
            assigned_by = %s,
            manager_comment = %s,
            assigned_at = NOW(),
            status = 'ASSIGNED',
            updated_at = NOW()
        WHERE id = %s
        """,
        (assigned_to, assigned_dept, req.action, actor, req.comment, assignment_id),
    )

    db_execute(
        "INSERT INTO decision_log (assignment_id, actor_id, action, payload) VALUES (%s, %s, %s, %s)",
        (
            assignment_id,
            actor,
            req.action,
            json.dumps({"assigned_to": assigned_to, "dept": assigned_dept, "comment": req.comment}),
        ),
    )

    # Complete manager_review user task in BPM
    bpm_instance_id = assignment.get("bpm_instance_id")
    if bpm_instance_id:
        task = bpm_find_user_task(bpm_instance_id, "manager")
        if task:
            task_id = task.get("id") or task.get("taskId")
            bpm_complete_user_task(
                task_id,
                [
                    {"name": "assignedTo", "value": assigned_to, "type": "STRING"},
                    {"name": "assignedDept", "value": assigned_dept, "type": "STRING"},
                    {"name": "assignmentAction", "value": req.action, "type": "STRING"},
                ],
            )
        else:
            logger.warning(f"No manager_review task found for instance {bpm_instance_id}")

    return {"status": "ok", "assigned_to": assigned_to, "assigned_dept": assigned_dept}


@app.post("/api/v1/assignments/{assignment_id}/dispute")
def dispute_assignment(assignment_id: str, req: DisputeRequest, executor_id: str = "executor1"):
    assignment = db_fetchone("SELECT * FROM assignments WHERE id = %s", (assignment_id,))
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    db_execute(
        """
        UPDATE assignments
        SET status = 'DISPUTED', disputed_dept = %s, manager_comment = %s, updated_at = NOW()
        WHERE id = %s
        """,
        (req.disputed_dept, req.comment, assignment_id),
    )

    db_execute(
        "INSERT INTO decision_log (assignment_id, actor_id, action, payload) VALUES (%s, %s, %s, %s)",
        (
            assignment_id,
            assignment.get("assigned_to", executor_id),
            "DISPUTED",
            json.dumps({"disputed_dept": req.disputed_dept, "comment": req.comment}),
        ),
    )

    logger.info(f"Assignment {assignment_id} disputed by executor → suggested dept: {req.disputed_dept}")
    return {"status": "ok"}


@app.post("/api/v1/assignments/{assignment_id}/accept")
def accept_assignment(assignment_id: str, executor_id: str = "executor1"):
    assignment = db_fetchone("SELECT * FROM assignments WHERE id = %s", (assignment_id,))
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    db_execute(
        "UPDATE assignments SET status = 'ACCEPTED', updated_at = NOW() WHERE id = %s",
        (assignment_id,),
    )

    db_execute(
        "INSERT INTO decision_log (assignment_id, actor_id, action, payload) VALUES (%s, %s, %s, %s)",
        (assignment_id, executor_id, "ACCEPTED", json.dumps({"executor_id": executor_id})),
    )

    # Complete executor_inbox user task in BPM
    bpm_instance_id = assignment.get("bpm_instance_id")
    if bpm_instance_id:
        task = bpm_find_user_task(bpm_instance_id, "executor")
        if task:
            task_id = task.get("id") or task.get("taskId")
            bpm_complete_user_task(
                task_id,
                [{"name": "executorDecision", "value": "ACCEPTED", "type": "STRING"}],
            )

    return {"status": "ok"}


@app.post("/api/v1/assignments/{assignment_id}/reject")
def reject_assignment(assignment_id: str, reason: str = ""):
    assignment = db_fetchone("SELECT * FROM assignments WHERE id = %s", (assignment_id,))
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    db_execute(
        "UPDATE assignments SET status = 'REJECTED', manager_comment = %s, updated_at = NOW() WHERE id = %s",
        (reason, assignment_id),
    )

    db_execute(
        "INSERT INTO decision_log (assignment_id, actor_id, action, payload) VALUES (%s, %s, %s, %s)",
        (
            assignment_id,
            assignment.get("assigned_to", "executor"),
            "REJECTED",
            json.dumps({"reason": reason}),
        ),
    )

    # Complete executor_inbox user task in BPM
    bpm_instance_id = assignment.get("bpm_instance_id")
    if bpm_instance_id:
        task = bpm_find_user_task(bpm_instance_id, "executor")
        if task:
            task_id = task.get("id") or task.get("taskId")
            bpm_complete_user_task(
                task_id,
                [
                    {"name": "executorDecision", "value": "REJECTED", "type": "STRING"},
                    {"name": "rejectReason", "value": reason, "type": "STRING"},
                ],
            )

    return {"status": "ok"}


@app.get("/api/v1/user-tasks/manager")
def get_manager_tasks():
    rows = db_fetchall(
        """
        SELECT * FROM assignments
        WHERE status IN ('NEW', 'CLASSIFIED', 'DISPUTED')
        ORDER BY
            CASE status WHEN 'DISPUTED' THEN 0 ELSE 1 END,
            CASE priority WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END,
            created_at ASC
        LIMIT 100
        """,
    )
    return [dict(r) for r in rows]


@app.get("/api/v1/user-tasks/executor/{executor_id}")
def get_executor_tasks(executor_id: str):
    rows = db_fetchall(
        """
        SELECT * FROM assignments
        WHERE assigned_to = %s AND status IN ('ASSIGNED', 'ACCEPTED', 'DISPUTED')
        ORDER BY created_at DESC
        LIMIT 100
        """,
        (executor_id,),
    )
    return [dict(r) for r in rows]


@app.get("/api/v1/dashboard/metrics")
def get_metrics():
    total = db_fetchone("SELECT COUNT(*) AS cnt FROM assignments", ())
    by_status = db_fetchall(
        "SELECT status, COUNT(*) AS cnt FROM assignments GROUP BY status ORDER BY cnt DESC",
    )
    by_dept = db_fetchall(
        """
        SELECT COALESCE(assigned_dept, suggested_dept, 'Unclassified') AS dept,
               COUNT(*) AS cnt
        FROM assignments
        GROUP BY 1
        ORDER BY cnt DESC
        """,
    )
    by_zone = db_fetchall(
        "SELECT confidence_zone, COUNT(*) AS cnt FROM assignments WHERE confidence_zone IS NOT NULL GROUP BY confidence_zone",
    )
    avg_confidence = db_fetchone(
        "SELECT ROUND(AVG(confidence)::numeric, 3) AS avg FROM assignments WHERE confidence IS NOT NULL",
        (),
    )
    return {
        "total": total["cnt"] if total else 0,
        "by_status": [dict(r) for r in by_status],
        "by_dept": [dict(r) for r in by_dept],
        "by_confidence_zone": [dict(r) for r in by_zone],
        "avg_confidence": float(avg_confidence["avg"]) if avg_confidence and avg_confidence["avg"] else 0,
    }


# ── Users ─────────────────────────────────────────────────────────────────────

@app.get("/api/v1/users")
def list_users():
    rows = db_fetchall(
        """
        SELECT u.*, d.code AS dept_code, d.name AS dept_name
        FROM users u
        LEFT JOIN departments d ON d.id = u.dept_id
        ORDER BY
            CASE u.role WHEN 'ADMIN' THEN 1 WHEN 'MANAGER' THEN 2 ELSE 3 END,
            d.code NULLS FIRST, u.name
        """
    )
    return [dict(r) for r in rows]


# ── Admin: Departments ───────────────────────────────────────────────────────

class DepartmentCreate(BaseModel):
    code: str
    name: str
    parent_id: Optional[str] = None
    functions_text: Optional[str] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[str] = None
    functions_text: Optional[str] = None
    archived: Optional[bool] = None


@app.get("/api/v1/admin/departments")
def admin_list_departments():
    rows = db_fetchall(
        "SELECT * FROM departments ORDER BY archived, code"
    )
    return [dict(r) for r in rows]


@app.post("/api/v1/admin/departments", status_code=201)
def admin_create_department(req: DepartmentCreate):
    existing = db_fetchone("SELECT id FROM departments WHERE code = %s", (req.code,))
    if existing:
        raise HTTPException(status_code=409, detail="Department code already exists")
    row = db_execute(
        """
        INSERT INTO departments (code, name, parent_id, functions_text)
        VALUES (%s, %s, %s, %s) RETURNING *
        """,
        (req.code, req.name, req.parent_id or None, req.functions_text),
    )
    return dict(row)


@app.put("/api/v1/admin/departments/{dept_id}")
def admin_update_department(dept_id: str, req: DepartmentUpdate):
    dept = db_fetchone("SELECT * FROM departments WHERE id = %s", (dept_id,))
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    updates = {
        "name": req.name if req.name is not None else dept["name"],
        "parent_id": req.parent_id if req.parent_id is not None else dept["parent_id"],
        "functions_text": req.functions_text if req.functions_text is not None else dept["functions_text"],
        "archived": req.archived if req.archived is not None else dept["archived"],
    }
    row = db_execute(
        """
        UPDATE departments SET name=%s, parent_id=%s, functions_text=%s, archived=%s, updated_at=NOW()
        WHERE id=%s RETURNING *
        """,
        (updates["name"], updates["parent_id"], updates["functions_text"], updates["archived"], dept_id),
    )
    return dict(row)


# ── Admin: Assignment Rights ──────────────────────────────────────────────────

@app.get("/api/v1/admin/rights")
def admin_list_rights():
    rows = db_fetchall(
        """
        SELECT r.id, r.from_dept_id, r.to_dept_id, r.created_at,
               f.code AS from_code, f.name AS from_name,
               t.code AS to_code, t.name AS to_name
        FROM assignment_rights r
        JOIN departments f ON f.id = r.from_dept_id
        JOIN departments t ON t.id = r.to_dept_id
        ORDER BY f.code, t.code
        """
    )
    return [dict(r) for r in rows]


@app.post("/api/v1/admin/rights", status_code=201)
def admin_add_right(from_dept_id: str, to_dept_id: str):
    if from_dept_id == to_dept_id:
        raise HTTPException(status_code=400, detail="Cannot assign to same department")
    for dept_id in (from_dept_id, to_dept_id):
        if not db_fetchone("SELECT id FROM departments WHERE id = %s AND NOT archived", (dept_id,)):
            raise HTTPException(status_code=404, detail=f"Department {dept_id} not found")
    try:
        row = db_execute(
            "INSERT INTO assignment_rights (from_dept_id, to_dept_id) VALUES (%s, %s) RETURNING *",
            (from_dept_id, to_dept_id),
        )
        return dict(row)
    except Exception:
        raise HTTPException(status_code=409, detail="Right already exists")


@app.delete("/api/v1/admin/rights")
def admin_delete_right(from_dept_id: str, to_dept_id: str):
    row = db_fetchone(
        "SELECT id FROM assignment_rights WHERE from_dept_id=%s AND to_dept_id=%s",
        (from_dept_id, to_dept_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Right not found")
    db_execute(
        "DELETE FROM assignment_rights WHERE from_dept_id=%s AND to_dept_id=%s",
        (from_dept_id, to_dept_id),
    )
    return {"status": "ok"}


# ── Background polling ────────────────────────────────────────────────────────

async def poll_lotus_mock():
    """Poll Lotus Notes mock for new assignments and create them in IAR."""
    logger.info("Lotus poll task started")
    while True:
        await asyncio.sleep(POLL_INTERVAL)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{LOTUS_MOCK_URL}/notes/assignments/new")
                resp.raise_for_status()
                new_assignments = resp.json()

            if not new_assignments:
                continue

            logger.info(f"Lotus poll: found {len(new_assignments)} new assignment(s)")

            for item in new_assignments:
                lotus_id = str(item.get("id", ""))

                # Check if already imported
                existing = db_fetchone(
                    "SELECT id FROM assignments WHERE lotus_id = %s", (lotus_id,)
                )
                if existing:
                    continue

                # Create assignment
                req = CreateAssignmentRequest(
                    text=item.get("text", ""),
                    author_id=item.get("author", "Руководитель"),
                    due_date=item.get("due_date"),
                    priority=item.get("priority", "MEDIUM"),
                    lotus_id=lotus_id,
                )
                create_assignment(req)

                # Mark as picked up in Lotus mock
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        await client.put(
                            f"{LOTUS_MOCK_URL}/notes/assignments/{lotus_id}/status",
                            json={"picked_up": True},
                        )
                except Exception as e:
                    logger.error(f"Failed to mark lotus assignment {lotus_id} as picked up: {e}")

        except Exception as e:
            logger.error(f"Lotus poll error: {e}")


@app.on_event("startup")
async def startup():
    asyncio.create_task(poll_lotus_mock())
    logger.info("IAR API started")
