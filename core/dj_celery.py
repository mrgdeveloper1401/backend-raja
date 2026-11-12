# core/dj_celery.py
import os
from celery import Celery
import celery_task_view.signals

from .settings import IS_WINDOWS

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery()
app.config_from_object("django.conf:settings", namespace="CELERY")

if IS_WINDOWS:
    app.conf.worker_pool = "solo"

app.autodiscover_tasks()
