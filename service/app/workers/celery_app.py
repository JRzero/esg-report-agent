try:
    from celery import Celery
    from app.core.config import get_settings
    s=get_settings(); celery_app=Celery('esg',broker=s.redis_url,backend=s.redis_url)
    celery_app.conf.task_routes={'app.workers.tasks.process_document':'documents','app.workers.tasks.run_ai_task':'ai','app.workers.tasks.export_report':'exports'}
except ImportError:
    class Dummy:
        def task(self,*a,**k):
            def dec(fn): return fn
            return dec
    celery_app=Dummy()
