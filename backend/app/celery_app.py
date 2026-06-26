#app/celery_app.py
from celery import Celery
from .config import settings

celery_app = Celery(
    "huanrong",
    broker=settings.CELERY_BROKER_URL,      # 例如 "redis://localhost:6379/0"
    backend=settings.CELERY_RESULT_BACKEND, # 例如 "redis://localhost:6379/1"
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
)