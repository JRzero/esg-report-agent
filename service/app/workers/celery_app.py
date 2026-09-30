try:
    from celery import Celery

    from app.core.config import get_settings

    settings = get_settings()
    celery_app = Celery("esg", broker=settings.redis_url, backend=settings.redis_url)
    celery_app.conf.update(
        task_routes={
            "app.workers.tasks.process_document": {"queue": "documents"},
            "app.workers.tasks.run_ai_task": {"queue": "ai"},
            "app.workers.tasks.reconcile_context_bindings": {"queue": "maintenance"},
            "app.workers.tasks.recover_stale_work": {"queue": "maintenance"},
        },
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_track_started=True,
        beat_schedule={
            "reconcile-openviking-context": {
                "task": "app.workers.tasks.reconcile_context_bindings",
                "schedule": 30.0,
            },
            "recover-stale-service-work": {
                "task": "app.workers.tasks.recover_stale_work",
                "schedule": 60.0,
            },
        },
    )
except ImportError:
    class DummyTask:
        def __init__(self, fn):
            self.fn = fn

        def __call__(self, *args, **kwargs):
            return self.fn(*args, **kwargs)

        def delay(self, *args, **kwargs):
            return self.fn(*args, **kwargs)

    class Dummy:
        def task(self, *args, **kwargs):
            def decorator(fn):
                return DummyTask(fn)

            return decorator

    celery_app = Dummy()
