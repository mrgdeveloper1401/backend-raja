# core/dj_celery.py
import os
from celery import Celery
import celery_task_view.signals

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery()
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
