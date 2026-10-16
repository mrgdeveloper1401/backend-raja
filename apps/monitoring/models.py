from django.db import models
from apps.core.models import TimestampMixin, SoftDeleteMixin


class Log(SoftDeleteMixin):
    class Level(models.TextChoices):
        DEBUG = "debug", "Debug"
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"
        CRITICAL = "critical", "Critical"

    order_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    worker_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO)
    message = models.TextField()
    extra = models.JSONField(default=dict, blank=True)  # stack trace، url، step
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "logs"
        indexes = [
            models.Index(fields=["level", "created_at"]),
        ]


class Notification(TimestampMixin):
    class Type(models.TextChoices):
        ORDER_SUCCESS = "order_success", "رزرو موفق"
        ORDER_FAILED = "order_failed", "رزرو ناموفق"
        CAPACITY_FOUND = "capacity_found", "ظرفیت پیدا شد"
        PRESALE_STARTED = "presale_started", "پیش‌فروش شروع شد"
        SYSTEM_ALERT = "system_alert", "هشدار سیستم"

    user_id = models.BigIntegerField()
    order_id = models.BigIntegerField(null=True, blank=True)
    type = models.CharField(max_length=30, choices=Type.choices)
    message = models.TextField()
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = "notifications"
        indexes = [
            models.Index(fields=["user_id", "is_read"]),
        ]
