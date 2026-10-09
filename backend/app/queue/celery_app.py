import asyncio
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "novel_translator_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    task_track_started=True,
)


@celery_app.task(name="tasks.translate_chapter_celery")
def translate_chapter_celery_task(job_id: str, chapter_id: int, force: bool = False):
    """Celery task entry point."""
    from app.queue.job_runner import execute_translation_job
    # Run async function in sync Celery worker
    asyncio.run(execute_translation_job(job_id, chapter_id, force))
    return {"status": "completed", "job_id": job_id}
