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
QUEUE = "zorrobpm.jobs.iar_notify"


def send_notification(assignment_id: str, assigned_to: str, assigned_dept: str, text_preview: str):
    """Mock notification sender — logs only, no real email."""
    logger.info("=" * 60)
    logger.info("NOTIFICATION")
    logger.info(f"  Assignment  : {assignment_id}")
    logger.info(f"  Assigned To : {assigned_to}")
    logger.info(f"  Department  : {assigned_dept}")
    logger.info(f"  Preview     : {text_preview[:120]}...")
    logger.info("=" * 60)


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
        assigned_to = variables.get("assignedTo", variables.get("suggestedExecutor", "unknown"))
        assigned_dept = variables.get("assignedDept", variables.get("suggestedDept", "unknown"))
        assignment_text = variables.get("assignmentText", "")

        # Fetch full assignment details from IAR API for richer notification
        if assignment_id:
            try:
                resp = httpx.get(
                    f"{IAR_API_URL}/api/v1/assignments/{assignment_id}",
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    assigned_to = data.get("assigned_to") or assigned_to
                    assigned_dept = data.get("assigned_dept") or assigned_dept
                    assignment_text = data.get("text") or assignment_text
            except Exception as e:
                logger.warning(f"Could not fetch assignment details: {e}")

        send_notification(assignment_id, assigned_to, assigned_dept, assignment_text)

        # Complete service task in ZorroBPM
        try:
            resp = httpx.post(
                f"{ZORROBPM_API}/service-tasks/{task_id}/complete",
                json={
                    "variables": [
                        {"name": "notificationSent", "value": "true", "type": "STRING"},
                        {"name": "notifiedAt", "value": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "type": "STRING"},
                    ]
                },
                timeout=10,
            )
            resp.raise_for_status()
            logger.info(f"Service task {task_id} completed")
        except Exception as e:
            logger.error(f"Failed to complete BPM service task {task_id}: {e}")

        ch.basic_ack(delivery_tag=method.delivery_tag)

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
    logger.info(f"Notify Worker starting, queue={QUEUE}")
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
