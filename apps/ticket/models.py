from django.db import models
from apps.core.models import TimestampMixin, SoftDeleteMixin
from django.utils.translation import gettext_lazy as _

from apps.user.models import User


class Passenger(TimestampMixin, SoftDeleteMixin):
    class Gender(models.TextChoices):
        MALE = "male", "مرد"
        FEMALE = "female", "زن"

    user = models.ForeignKey(
        User, on_delete=models.DO_NOTHING, related_name="passengers"
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    national_id = models.CharField(max_length=10)
    gender = models.CharField(max_length=10, choices=Gender.choices)
    birth_date = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=15)

    class Meta:
        db_table = "passengers"


class Order(TimestampMixin, SoftDeleteMixin):
    class Status(models.TextChoices):
        PENDING = "pending", _("در انتظار پرداخت")
        PAID = "paid", _("پرداخت شده")
        BOOKED = "booked", _("رزرو قطعی در سامانه")
        FAILED = "failed", _("شکست خورده")

    passenger = models.ForeignKey(
        Passenger,
        on_delete=models.DO_NOTHING,
        related_name="passenger_orders",
        db_index=False,
    )
    origin = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    travel_date = models.DateField()
    status = models.CharField(
        max_length=20, default=Status.PENDING, choices=Status.choices
    )
    train_number = models.CharField(max_length=50, blank=True, null=True)  # شماره قطار

    class Meta:
        db_table = "orders"


# جدول میانی برای اتصال مسافران به یک سفارش همراه با نوع سهمیه/نرخ
class OrderItem(TimestampMixin, SoftDeleteMixin):
    class PassengerType(models.TextChoices):
        MAN = "man", _("ویژه برادران")
        WOMAN = "woman", _("ویژه خواهران")
        NORMAL = "normal", _("مسافرین عادی")

    order = models.ForeignKey(Order, on_delete=models.DO_NOTHING, related_name="items")
    passenger = models.ForeignKey(
        Passenger, on_delete=models.DO_NOTHING, related_name="order_items"
    )
    passenger_type = models.CharField(
        max_length=20, default=PassengerType.NORMAL, choices=PassengerType.choices
    )
    is_adult = models.BooleanField(default=True)
    price = models.DecimalField(
        max_digits=12, decimal_places=0, default=0
    )  # قیمت به ریال

    class Meta:
        db_table = "order_items"
