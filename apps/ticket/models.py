from django.contrib.postgres.fields import ArrayField
from django.db import models
from apps.core.models import TimestampMixin, SoftDeleteMixin


class Passenger(TimestampMixin, SoftDeleteMixin):
    class Gender(models.TextChoices):
        MALE = "male", "مرد"
        FEMALE = "female", "زن"

    user_id = models.BigIntegerField(db_index=True)  # ref to accounts.User
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    national_id = models.CharField(max_length=10)
    gender = models.CharField(max_length=10, choices=Gender.choices)
    birth_date = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=15)
    is_verified = models.BooleanField(default=False)  # کد ملی تایید شده

    class Meta:
        db_table = "passengers"
        unique_together = [("user_id", "national_id")]

    # def __str__(self):
    #     return f"{self.first_name} {self.last_name} ({self.national_id})"


class Order(TimestampMixin, SoftDeleteMixin):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار"
        MONITORING = "monitoring", "در حال پایش"
        PROCESSING = "processing", "در حال رزرو"
        SUCCESS = "success", "موفق"
        FAILED = "failed", "ناموفق"
        CANCELLED = "cancelled", "لغو شده"
        PAID_STEP = "paid_step", "موفق تا مرحله پرداخت"

    user_id = models.BigIntegerField(db_index=True)  # ref to accounts.User
    origin = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    travel_date = models.DateField()
    passenger_count = models.PositiveSmallIntegerField()
    price_min = models.PositiveBigIntegerField(null=True, blank=True)
    price_max = models.PositiveBigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Pre-sale
    is_presale = models.BooleanField(default=False)
    presale_open_at = models.DateTimeField(null=True, blank=True)

    # نتیجه نهایی
    result_detail = models.JSONField(default=dict, blank=True)
    failure_reason = models.TextField(blank=True)

    class Meta:
        db_table = "orders"
        indexes = [
            models.Index(fields=["user_id", "status"]),
            models.Index(fields=["travel_date", "status"]),
        ]

    # def __str__(self):
    #     return f"#{self.pk} {self.origin}→{self.destination} ({self.status})"


class TrainFilter(TimestampMixin, SoftDeleteMixin):
    """فیلترهای مربوط به یک سفارش"""

    class SeatType(models.TextChoices):
        COMPARTMENT_6 = "6_berth", "۶ تخته"
        SALOON = "saloon", "سالنی"
        STAR_3 = "star_3", "سه ستاره"
        STAR_4 = "star_4", "چهار ستاره"
        STAR_5 = "star_5", "پنج ستاره"

    order_id = models.OneToOneField(
        Order, on_delete=models.DO_NOTHING, related_name="train_filter", db_column="order_id"
    )
    train_numbers = ArrayField(models.CharField(max_length=20), blank=True, default=list)
    seat_types = ArrayField(
        models.CharField(max_length=20, choices=SeatType.choices), blank=True, default=list
    )
    departure_time_ranges = models.JSONField(
        default=list, blank=True,
        help_text='مثال: [{"start": "18:00", "end": "21:00"}]'
    )

    class Meta:
        db_table = "train_filters"


class OrderPassenger(SoftDeleteMixin, TimestampMixin):
    """رابط چند به چند سفارش و مسافر"""
    order = models.ForeignKey(Order, on_delete=models.DO_NOTHING)
    passenger = models.ForeignKey(Passenger, on_delete=models.DO_NOTHING)
    seat_number = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = "order_passengers"
        unique_together = [("order", "passenger_id")]
