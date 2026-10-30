from django.db import models
from django.utils import timezone

from apps.core.managers import SoftDeleteManager


class TimestampMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)
    is_deleted = models.BooleanField(null=True, blank=True, editable=False)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])


class Station(models.Model):
    code = models.PositiveIntegerField(unique=True, verbose_name="کد ایستگاه")
    name = models.CharField(max_length=255, verbose_name="نام")
    english_name = models.CharField(
        max_length=255, blank=True, default="", verbose_name="نام انگلیسی"
    )
    tel_code = models.CharField(
        max_length=20, blank=True, default="", verbose_name="کد تلفن"
    )
    group = models.CharField(
        max_length=255, blank=True, default="", verbose_name="گروه"
    )
    is_car_ticket = models.BooleanField(default=False, verbose_name="حمل خودرو")
    is_exclusion = models.BooleanField(default=False, verbose_name="استثنا")

    class Meta:
        db_table = "station"
        verbose_name = "ایستگاه"
        verbose_name_plural = "ایستگاه‌ها"
