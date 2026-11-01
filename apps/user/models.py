from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    UserManager,
)
from django.db import models

from apps.core.managers import SoftDeleteQuerySet
from apps.core.models import TimestampMixin, SoftDeleteMixin


class CustomUserManager(UserManager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()


class User(AbstractBaseUser, PermissionsMixin, TimestampMixin, SoftDeleteMixin):
    phone = models.CharField(max_length=15, unique=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    username = models.CharField(max_length=32, unique=True, blank=True, null=True)
    email = models.EmailField(max_length=255, blank=True, null=True)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = (
        "email",
        "username",
    )

    objects = CustomUserManager()

    class Meta:
        db_table = "accounts_users"

    # def __str__(self):
    #     return f"{self.phone} ({self.role})"


class RajaAccount(TimestampMixin):
    """اطلاعات اکانت رجا برای ورود ربات"""

    username = models.CharField(max_length=20, verbose_name="شماره همراه رجا")
    password = models.CharField(max_length=100, verbose_name="رمز عبور رجا")
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    # اینجا می‌تونیم سشن لاگین شده رو هم ذخیره کنیم
    session_json = models.TextField(
        blank=True, null=True, verbose_name="سشن ذخیره شده (JSON)"
    )

    class Meta:
        db_table = "raja_accounts"
        verbose_name = "اکانت رجا"
        verbose_name_plural = "اکانت‌های رجا"
