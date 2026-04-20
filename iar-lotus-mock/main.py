import os
import logging
from datetime import datetime
from typing import Optional

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Lotus Notes Mock")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL")


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

class CreateAssignment(BaseModel):
    text: str
    author: str = "Руководитель"
    due_date: Optional[str] = None
    priority: str = "MEDIUM"


class UpdateStatus(BaseModel):
    picked_up: Optional[bool] = None
    status: Optional[str] = None


# ── HTML helpers ──────────────────────────────────────────────────────────────

def render_page(assignments_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Lotus Notes Mock — IAR</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #f0f2f5; color: #333; }}
    .header {{ background: #c8102e; color: white; padding: 14px 32px;
               display: flex; align-items: center; gap: 16px; }}
    .header h1 {{ font-size: 20px; font-weight: 700; }}
    .header span {{ font-size: 13px; opacity: 0.8; }}
    .main {{ max-width: 900px; margin: 32px auto; padding: 0 16px; }}
    .card {{ background: white; border-radius: 10px; padding: 28px;
             box-shadow: 0 2px 8px rgba(0,0,0,.08); margin-bottom: 28px; }}
    .card h2 {{ font-size: 17px; margin-bottom: 20px; color: #1a1a2e; }}
    .form-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .form-full {{ grid-column: 1 / -1; }}
    label {{ display: block; font-size: 13px; font-weight: 600;
             color: #555; margin-bottom: 5px; }}
    textarea, input[type=text], input[type=date], select {{
      width: 100%; padding: 9px 12px; border: 1px solid #d1d5db;
      border-radius: 6px; font-size: 14px; font-family: inherit;
      background: #fafafa; transition: border-color .2s;
    }}
    textarea:focus, input:focus, select:focus {{
      outline: none; border-color: #c8102e; background: white;
    }}
    textarea {{ resize: vertical; min-height: 100px; }}
    .btn {{ display: inline-block; padding: 10px 24px; background: #c8102e;
            color: white; border: none; border-radius: 6px; cursor: pointer;
            font-size: 14px; font-weight: 600; margin-top: 8px;
            transition: background .2s; }}
    .btn:hover {{ background: #a50d26; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th {{ text-align: left; padding: 10px 12px; background: #f8f9fa;
          border-bottom: 2px solid #e5e7eb; font-size: 12px;
          text-transform: uppercase; color: #6b7280; letter-spacing: .05em; }}
    td {{ padding: 10px 12px; border-bottom: 1px solid #f3f4f6; vertical-align: top; }}
    tr:hover td {{ background: #fafafa; }}
    .badge {{ display: inline-block; padding: 2px 9px; border-radius: 10px;
              font-size: 11px; font-weight: 600; }}
    .badge-new {{ background: #dbeafe; color: #1e40af; }}
    .badge-picked {{ background: #dcfce7; color: #166534; }}
    .badge-high {{ background: #fee2e2; color: #991b1b; }}
    .badge-medium {{ background: #fef9c3; color: #854d0e; }}
    .badge-low {{ background: #f3f4f6; color: #6b7280; }}
    .text-muted {{ color: #9ca3af; font-size: 12px; }}
    .empty {{ text-align: center; color: #9ca3af; padding: 32px;
              font-size: 14px; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>&#127381; Lotus Notes Mock</h1>
    <span>Симулятор входящих поручений для IAR</span>
  </div>
  <div class="main">
    <div class="card">
      <h2>Создать новое поручение</h2>
      <form method="POST" action="/notes/assignments/form">
        <div class="form-grid">
          <div class="form-full">
            <label for="text">Текст поручения</label>
            <textarea id="text" name="text" placeholder="Введите текст поручения..." required></textarea>
          </div>
          <div>
            <label for="author">Автор</label>
            <input type="text" id="author" name="author" value="Руководитель"/>
          </div>
          <div>
            <label for="priority">Приоритет</label>
            <select id="priority" name="priority">
              <option value="LOW">Низкий</option>
              <option value="MEDIUM" selected>Средний</option>
              <option value="HIGH">Высокий</option>
            </select>
          </div>
          <div>
            <label for="due_date">Срок исполнения</label>
            <input type="date" id="due_date" name="due_date"/>
          </div>
        </div>
        <button type="submit" class="btn">Отправить поручение</button>
      </form>
    </div>
    <div class="card">
      <h2>Последние поручения</h2>
      {assignments_html}
    </div>
  </div>
</body>
</html>"""


def build_assignments_table(rows) -> str:
    if not rows:
        return '<div class="empty">Поручений пока нет</div>'

    priority_map = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
    priority_label = {"HIGH": "Высокий", "MEDIUM": "Средний", "LOW": "Низкий"}

    html = """<table>
    <thead>
      <tr>
        <th>Текст</th>
        <th>Автор</th>
        <th>Приоритет</th>
        <th>Срок</th>
        <th>Статус</th>
        <th>Создано</th>
      </tr>
    </thead>
    <tbody>"""

    for r in rows:
        text_preview = (r["text"] or "")[:80] + ("..." if len(r["text"] or "") > 80 else "")
        status_badge = (
            '<span class="badge badge-picked">Забрано IAR</span>'
            if r["picked_up"]
            else '<span class="badge badge-new">Ожидает</span>'
        )
        due = r["due_date"].strftime("%d.%m.%Y") if r.get("due_date") else "—"
        created = r["created_at"].strftime("%d.%m.%Y %H:%M") if r.get("created_at") else "—"
        p = r.get("priority", "MEDIUM")
        prio_badge = f'<span class="badge badge-{priority_map.get(p, "medium")}">{priority_label.get(p, p)}</span>'

        html += f"""
      <tr>
        <td>{text_preview}</td>
        <td>{r.get('author', '—')}</td>
        <td>{prio_badge}</td>
        <td>{due}</td>
        <td>{status_badge}</td>
        <td class="text-muted">{created}</td>
      </tr>"""

    html += "\n    </tbody>\n</table>"
    return html


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    rows = db_fetchall(
        "SELECT * FROM lotus_assignments ORDER BY created_at DESC LIMIT 10"
    )
    table_html = build_assignments_table(rows)
    return render_page(table_html)


@app.post("/notes/assignments")
def create_assignment_json(req: CreateAssignment):
    due_date = None
    if req.due_date:
        try:
            due_date = datetime.fromisoformat(req.due_date)
        except Exception:
            due_date = None

    row = db_execute(
        """
        INSERT INTO lotus_assignments (text, author, due_date, priority, picked_up)
        VALUES (%s, %s, %s, %s, FALSE)
        RETURNING *
        """,
        (req.text, req.author, due_date, req.priority),
    )
    logger.info(f"Created lotus assignment {row['id']}")
    return dict(row)


@app.post("/notes/assignments/form")
def create_assignment_form(
    text: str = Form(...),
    author: str = Form("Руководитель"),
    due_date: str = Form(""),
    priority: str = Form("MEDIUM"),
):
    due = None
    if due_date:
        try:
            due = datetime.fromisoformat(due_date)
        except Exception:
            due = None

    db_execute(
        """
        INSERT INTO lotus_assignments (text, author, due_date, priority, picked_up)
        VALUES (%s, %s, %s, %s, FALSE)
        """,
        (text, author, due, priority),
    )
    return RedirectResponse(url="/", status_code=303)


@app.get("/notes/assignments/new")
def get_new_assignments():
    rows = db_fetchall(
        "SELECT * FROM lotus_assignments WHERE picked_up = FALSE ORDER BY created_at ASC"
    )
    return [dict(r) for r in rows]


@app.get("/notes/assignments")
def get_all_assignments():
    rows = db_fetchall(
        "SELECT * FROM lotus_assignments ORDER BY created_at DESC LIMIT 100"
    )
    return [dict(r) for r in rows]


@app.put("/notes/assignments/{assignment_id}/status")
def update_assignment_status(assignment_id: str, req: UpdateStatus):
    row = db_fetchone(
        "SELECT id FROM lotus_assignments WHERE id = %s", (assignment_id,)
    )
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Assignment not found")

    if req.picked_up is not None:
        db_execute(
            "UPDATE lotus_assignments SET picked_up = %s WHERE id = %s",
            (req.picked_up, assignment_id),
        )

    updated = db_fetchone(
        "SELECT * FROM lotus_assignments WHERE id = %s", (assignment_id,)
    )
    logger.info(f"Updated lotus assignment {assignment_id}: picked_up={req.picked_up}")
    return dict(updated)
