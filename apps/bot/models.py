from django.db import models
from apps.core.models import TimestampMixin, SoftDeleteMixin


class Server(TimestampMixin, SoftDeleteMixin):
    class HealthStatus(models.TextChoices):
        HEALTHY = "healthy", "سالم"
        DEGRADED = "degraded", "با مشکل"
        DOWN = "down", "خاموش"

    name = models.CharField(max_length=100, unique=True)
    host = models.CharField(max_length=255)
    max_workers = models.PositiveSmallIntegerField(default=5)
    is_active = models.BooleanField(default=True)
    health_status = models.CharField(
        max_length=20, choices=HealthStatus.choices, default=HealthStatus.HEALTHY
    )
    last_checked_at = models.DateTimeField(null=True, blank=True)
    celery_queue = models.CharField(max_length=100)  # نام queue اختصاصی این سرور

    class Meta:
        db_table = "servers"

    # def __str__(self):
    #     return f"{self.name} ({self.host})"

    @property
    def active_worker_count(self):
        return self.workers.filter(status=Worker.Status.RUNNING).count()

    @property
    def has_capacity(self):
        return self.active_worker_count < self.max_workers


class Worker(TimestampMixin, SoftDeleteMixin):
    class Status(models.TextChoices):
        IDLE = "idle", "بیکار"
        RUNNING = "running", "در حال اجرا"
        PAUSED = "paused", "متوقف موقت"
        SUCCESS = "success", "موفق"
        FAILED = "failed", "ناموفق"
        RECOVERING = "recovering", "در حال بازیابی"

    order_id = models.BigIntegerField()  # ref to orders.Order
    server = models.ForeignKey(
        Server, on_delete=models.SET_NULL, null=True, related_name="workers"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.IDLE
    )
    celery_task_id = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)

    class Meta:
        db_table = "workers"
        indexes = [
            models.Index(fields=["order_id", "status"]),
        ]


class BotSession(TimestampMixin, SoftDeleteMixin):
    """Session مرورگر برای هر سرور — Session Pool"""

    class Status(models.TextChoices):
        ACTIVE = "active", "فعال"
        EXPIRED = "expired", "منقضی"
        REFRESHING = "refreshing", "در حال تجدید"

    server = models.ForeignKey(
        Server, on_delete=models.DO_NOTHING, related_name="bot_sessions"
    )
    cookies = models.JSONField(default=dict)  # سریال‌شده در Redis هم نگه داشته می‌شود
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "bot_sessions"
