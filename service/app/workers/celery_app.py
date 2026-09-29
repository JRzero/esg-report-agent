from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery("esg", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_routes = {
    "app.workers.tasks.process_document": "documents",
    "app.workers.tasks.run_ai_task": "ai",
}
if settings.app_env == "test":
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
