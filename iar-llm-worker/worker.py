import pika
import json
import os
import time
import logging
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://demo:demo@rabbitmq:5672/")
ZORROBPM_API = os.getenv("ZORROBPM_API", "http://api")
IAR_API_URL = os.getenv("IAR_API_URL", "http://iar-api:8000")
QUEUE = "zorrobpm.jobs.iar_classify"

# Mock departments keyword mapping
DEPT_KEYWORDS = {
    "ДОЭ": [
        "эффективность", "операционн", "оптимизац", "процесс", "kpi",
        "реинжиниринг", "затрат", "нормировани", "производительност",
    ],
    "ДУКО": [
        "клиент", "сервис", "опыт", "обращение", "nps", "жалоб",
        "удовлетвор", "поддержк", "пользовател",
    ],
    "ДПОТ": [
        "проект", "трансформац", "цифровиз", "дорожная карта", "agile",
        "инициатив", "стратег", "портфел", "скрам", "scrum",
    ],
    "УДЦТиЭ": [
        "цифров", "технолог", "инновац", "автоматиз", "систем",
        "it ", " it", "платформ", "роботиз", "интеграц",
    ],
}

DEPT_EMPLOYEES = {
    "ДОЭ": [{"id": "EMP_001", "name": "Алексей Петров", "position": "Главный менеджер по операционной эффективности"}],
    "ДУКО": [{"id": "EMP_002", "name": "Мария Иванова", "position": "Менеджер по клиентскому опыту"}],
    "ДПОТ": [{"id": "EMP_003", "name": "Дмитрий Сидоров", "position": "Менеджер проектов трансформации"}],
    "УДЦТиЭ": [{"id": "EMP_004", "name": "Елена Козлова", "position": "Управляющий директор цифровых технологий"}],
}

DEPT_FUNCTIONS = {
    "ДОЭ":    "реинжиниринг бизнес-процессов, контроль KPI, оптимизация затрат, нормирование труда, операционный аудит",
    "ДУКО":   "обслуживание клиентов, управление NPS, обработка жалоб и обращений, клиентский сервис, удовлетворённость пользователей",
    "ДПОТ":   "управление проектами, цифровая трансформация, разработка дорожных карт, Agile/Scrum, стратегические инициативы",
    "УДЦТиЭ": "цифровые технологии, IT-платформы, автоматизация и роботизация процессов, технологические инновации, системная интеграция",
}


def mock_classify(text: str) -> dict:
    """Keyword-based mock LLM classifier."""
    text_lower = text.lower()
    scores = {}
    matched = {}
    for dept, keywords in DEPT_KEYWORDS.items():
        hits = [kw for kw in keywords if kw in text_lower]
        scores[dept] = len(hits)
        matched[dept] = hits

    total = sum(scores.values())

    if total == 0:
        dept = "ДОЭ"
        confidence = 0.35
    else:
        dept = max(scores, key=scores.get)
        confidence = min(0.95, 0.45 + scores[dept] / total * 0.55)

    zone = "GREEN" if confidence >= 0.8 else ("YELLOW" if confidence >= 0.5 else "RED")

    sorted_depts = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top3 = [
        {
            "department_code": d,
            "confidence": round(scores[d] / max(total, 1) * confidence, 2),
        }
        for d, _ in sorted_depts[:3]
    ]

    executor = DEPT_EMPLOYEES.get(
        dept,
        [{"id": "EMP_001", "name": "Алексей Петров", "position": "Главный менеджер"}],
    )[0]

    kw_line = (
        f"Ключевые слова в тексте: {', '.join(matched[dept])}"
        if matched[dept] else "Явных ключевых слов не найдено (низкая уверенность)"
    )
    func_line = f"Функции {dept}: {DEPT_FUNCTIONS[dept]}"
    exec_line = f"Исполнитель: {executor['name']} ({executor['position']}), уверенность {round(confidence * 100)}%"

    return {
        "suggested_dept": dept,
        "suggested_executor": executor["id"],
        "executor_name": executor["name"],
        "confidence": round(confidence, 3),
        "confidence_zone": zone,
        "justification": f"{kw_line}\n{func_line}\n{exec_line}",
        "top3_json": top3,
    }


def process_message(ch, method, properties, body):
    try:
        job = json.loads(body)
        task_id = job.get("taskId") or job.get("id", "")
        variables_raw = job.get("variables", {})

        # ZorroBPM may send variables as list or dict
        if isinstance(variables_raw, list):
            variables = {v["name"]: v.get("value") for v in variables_raw}
        else:
            variables = variables_raw

        assignment_id = variables.get("assignmentId", "")
        text = variables.get("assignmentText", "")

        logger.info(f"Classifying assignment {assignment_id}")
        result = mock_classify(text)

        # Save classification to IAR API
        try:
            resp = httpx.post(
                f"{IAR_API_URL}/api/v1/assignments/{assignment_id}/classification",
                json=result,
                timeout=10,
            )
            resp.raise_for_status()
            logger.info(f"Classification saved for {assignment_id}")
        except Exception as e:
            logger.error(f"Failed to save classification: {e}")

        # Complete service task in ZorroBPM
        try:
            resp = httpx.post(
                f"{ZORROBPM_API}/service-tasks/{task_id}/complete",
                json={
                    "variables": [
                        {"name": "suggestedDept", "value": result["suggested_dept"], "type": "STRING"},
                        {"name": "suggestedExecutor", "value": result["suggested_executor"], "type": "STRING"},
                        {"name": "confidence", "value": int(result["confidence"] * 100), "type": "LONG"},
                        {"name": "confidenceZone", "value": result["confidence_zone"], "type": "STRING"},
                        {"name": "justification", "value": result["justification"], "type": "STRING"},
                    ]
                },
                timeout=10,
            )
            resp.raise_for_status()
            logger.info(f"Service task {task_id} completed")
        except Exception as e:
            logger.error(f"Failed to complete BPM service task {task_id}: {e}")

        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(
            f"Classified {assignment_id} -> {result['suggested_dept']} ({result['confidence_zone']}, {result['confidence']})"
        )

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def connect_with_retry(url: str, max_attempts: int = 10, delay: int = 5):
    """Connect to RabbitMQ with retry logic."""
    params = pika.URLParameters(url)
    for attempt in range(1, max_attempts + 1):
        try:
            connection = pika.BlockingConnection(params)
            logger.info(f"Connected to RabbitMQ on attempt {attempt}")
            return connection
        except Exception as e:
            logger.warning(f"RabbitMQ connection attempt {attempt}/{max_attempts} failed: {e}")
            if attempt < max_attempts:
                time.sleep(delay)
    raise RuntimeError(f"Could not connect to RabbitMQ after {max_attempts} attempts")


def main():
    logger.info(f"LLM Worker starting, queue={QUEUE}")
    while True:
        try:
            connection = connect_with_retry(RABBITMQ_URL)
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE, on_message_callback=process_message)
            logger.info(f"Listening on {QUEUE} ...")
            channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Worker stopped")
            break
        except Exception as e:
            logger.error(f"Worker error, restarting: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
