from django.db import models
from apps.core.models import TimestampMixin, SoftDeleteMixin
from django.utils.translation import gettext_lazy as _

from apps.user.models import RajaAccount


class Passenger(TimestampMixin, SoftDeleteMixin):
    class Gender(models.TextChoices):
        MALE = "male", "مرد"
        FEMALE = "female", "زن"

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    national_id = models.CharField(max_length=10)
    gender = models.CharField(max_length=10, choices=Gender.choices)
    birth_date = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=15)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        db_table = "passengers"
        verbose_name = _("مسافر")
        verbose_name_plural = _("مسافران")


class Order(TimestampMixin, SoftDeleteMixin):
    class PassengerType(models.TextChoices):
        MAN = "man", _("ویژه برادران")
        WOMAN = "woman", _("ویژه خواهران")
        NORMAL = "normal", _("مسافرین عادی")

    passenger = models.ForeignKey(
        Passenger,
        on_delete=models.DO_NOTHING,
        related_name="passenger_orders",
        db_index=False,
    )
    origin = models.CharField(max_length=100, verbose_name="مبدا")
    destination = models.CharField(max_length=100, verbose_name="مقصد")
    travel_date = models.DateField(verbose_name="تاریخ سفر")
    passenger_type = models.CharField(
        max_length=20,
        choices=PassengerType.choices,
        default=PassengerType.NORMAL,
        verbose_name="نوع بلیط",
    )

    class Meta:
        db_table = "orders"
        verbose_name = _("سفارش")
        verbose_name_plural = _("سفارش‌ها")


class OrderItem(TimestampMixin, SoftDeleteMixin):
    """جدول واسط برای مسافران هر سفارش"""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    passenger = models.ForeignKey(
        Passenger, on_delete=models.PROTECT, related_name="order_items"
    )
    is_adult = models.BooleanField(default=True, help_text=_("بزرگسال هست؟"))

    class Meta:
        db_table = "order_items"
        verbose_name = "آیتم سفارش"
        verbose_name_plural = "آیتم‌های سفارش"


class Reservation(TimestampMixin, SoftDeleteMixin):
    class ReservationStatus(models.TextChoices):
        PENDING = "pending", _("انتظار")
        MONITORING = "monitoring", _("در حال رصد")
        BOOKING = "booking", _("در حال رزرو")
        REDIRECT_GATEWAY = "redirect_gateway", _("هدایت به درگاه پرداخت")
        SUCCESS = "success", _("موفق")
        FAILED = "failed", _("ناموفق")

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="reservations",
        verbose_name="سفارش",
    )
    raja_account = models.ForeignKey(
        RajaAccount, on_delete=models.DO_NOTHING, verbose_name="اکانت رجا"
    )
    status = models.CharField(
        max_length=20,
        choices=ReservationStatus.choices,
        default=ReservationStatus.PENDING,
        verbose_name="وضعیت",
    )
    payment_url = models.URLField(
        blank=True, null=True, verbose_name="لینک درگاه پرداخت"
    )
    error_message = models.TextField(blank=True, null=True, verbose_name="پیام خطا")

    class Meta:
        db_table = "reservations"
        verbose_name = "رزرو"
        verbose_name_plural = "رزروها"
