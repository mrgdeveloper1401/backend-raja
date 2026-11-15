from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TimestampMixin, SoftDeleteMixin
from django.utils.translation import gettext_lazy as _

from apps.user.models import RajaAccount


class ReservationStatus(models.TextChoices):
    PENDING = "pending", _("انتظار")
    MONITORING = "monitoring", _("در حال رصد")
    BOOKING = "booking", _("در حال رزرو")
    REDIRECT_GATEWAY = "redirect_gateway", _("هدایت به درگاه پرداخت")
    SUCCESS = "success", _("موفق")
    FAILED = "failed", _("ناموفق")
    CAPTCHA = "captcha", _("حل کپچا")


class RestitutionEnum(models.TextChoices):
    SUCCESS = "success", _("موفق")
    FAILED = "failed", _("ناموفق")
    PENDING = "pending", _("انتظار")


class SalonType(models.TextChoices):
    FOUR_STAR_FOUR_COUPE = "4_star_4_coupe", _("4 ستاره 4 تخته")
    FOUR_STAR_FIVE_COUPE = "4_star_5_coupe", _("4 ستاره 5 تخته")  # طبق درخواست شما
    FIVE_STAR = "5_star", _("5 ستاره")
    THREE_STAR_SIX_COUPE = "3_star_6_coupe", _("3 ستاره 6 تخته")


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

    class TripType(models.TextChoices):
        OUT_BOUND = "outbound", _("تک سفر")
        OUT_BOUND_AND_RETURN = "outbound_and_return", _("مسیر رفت و برگشت")

    passenger = models.ForeignKey(
        Passenger,
        on_delete=models.DO_NOTHING,
        related_name="passenger_orders",
        db_index=False,
    )
    origin = models.CharField(max_length=100, verbose_name="مبدا")
    destination = models.CharField(max_length=100, verbose_name="مقصد")
    trip_type = models.CharField(
        max_length=20, choices=TripType.choices, default=TripType.OUT_BOUND
    )
    travel_date = models.DateField(
        verbose_name="تاریخ سفر",
        blank=True,
        null=True,
        help_text=_(
            "تاریخ سفر برای هنگامی که مسیر فقط برای تک سفر باشد یا برای مسیر رفت درون سفرهای رفت و برگشت"
        ),
    )
    to_date = models.DateField(_("تاریخ برگشت"), blank=True, null=True)
    passenger_type = models.CharField(
        max_length=20,
        choices=PassengerType.choices,
        default=PassengerType.NORMAL,
        verbose_name="نوع بلیط",
    )

    def clean(self):
        if self.trip_type == self.TripType.OUT_BOUND and self.to_date:
            raise ValidationError(_("حالت تک سفره مسیر برگشت ندارد"))
        if self.trip_type == self.TripType.OUT_BOUND_AND_RETURN and self.travel_date:
            if not self.to_date:
                raise ValidationError(_("برای مسیر رفت و برگشت تاریخ برگشت الزامی است"))
            if self.to_date < self.travel_date:
                raise ValidationError(
                    _("تاریخ برگشت نمیتواند کوچک تر از تاریخ رفت باشد")
                )
        if self.travel_date < timezone.now().date():
            raise ValidationError(_("تاریخ رفت نمیتواند کوچک تر از تاریخ امروز باشد"))
        if self.to_date and self.to_date < timezone.now().date():
            raise ValidationError(_("تاریخ برگشت نمیتواند کوچک تر از تایم امروز باشد"))

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
    class CoupeType(models.TextChoices):
        FOUR = "four", _("چهار  تخته")
        SIX = "six", _("شش تخته")
        FOR_ROW = "for_row", _("چهار ردیفه")

    class OrderBy(models.TextChoices):
        CLOCK = "clock", _("ساعت حرکت")
        CHEAP = "cheap", _("ارزان ترین")
        EXPENSIVE = "expensive", _("گران ترین")
        OWNER = "owner", _("مالک")

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="reservations",
        verbose_name="سفارش",
    )
    raja_account = models.ForeignKey(
        RajaAccount, on_delete=models.CASCADE, verbose_name="اکانت رجا"
    )
    coupe_type = models.CharField(
        _("نوع کوپه"), max_length=8, blank=True, null=True, choices=CoupeType.choices
    )
    order_by = models.CharField(
        _("فیلتر بر اساس"),
        max_length=15,
        blank=True,
        null=True,
        choices=OrderBy.choices,
        default=OrderBy.CLOCK,
    )
    is_exclusive = models.BooleanField(_("کوپه دربست"), default=False, db_default=False)
    # زمان حرکت (قطار رفت)
    departure_time_from = models.PositiveSmallIntegerField(
        _("زمان حرکت (از)"),
        blank=True,
        null=True,
        help_text=_("بازه زمانی حضور قطار در ایستگاه مبدا (شروع)"),
    )
    departure_time_to = models.PositiveSmallIntegerField(
        _("زمان حرکت (تا)"),
        blank=True,
        null=True,
        help_text=_("بازه زمانی حضور قطار در ایستگاه مبدا (پایان)"),
    )

    # زمان ورود به ایستگاه (مقصد)
    arrival_time_from = models.PositiveSmallIntegerField(
        _("زمان ورود به ایستگاه (از)"),
        blank=True,
        null=True,
        help_text=_("زمان تقریبی ورود به ایستگاه مقصد (شروع)"),
    )
    arrival_time_to = models.PositiveSmallIntegerField(
        _("زمان ورود به ایستگاه (تا)"),
        blank=True,
        null=True,
        help_text=_("زمان تقریبی ورود به ایستگاه مقصد (پایان)"),
    )

    from_price = models.DecimalField(
        blank=True, null=True, max_digits=10, decimal_places=2
    )
    to_price = models.DecimalField(
        blank=True, null=True, max_digits=10, decimal_places=2
    )
    train_number = models.CharField(
        _("شماره قطار"), blank=True, max_length=10, null=True
    )

    adult_number = models.PositiveSmallIntegerField(default=1, db_default=1)
    baby_number = models.PositiveSmallIntegerField(default=0, db_default=0)

    salon = models.CharField(
        _("سالن"), max_length=50, blank=True, null=True, choices=SalonType.choices
    )

    class Meta:
        db_table = "reservations"
        verbose_name = "رزرو"
        verbose_name_plural = "رزروها"


class ReservationAttempt(TimestampMixin, SoftDeleteMixin):
    reservation = models.ForeignKey(
        Reservation, on_delete=models.CASCADE, related_name="attempts"
    )
    status = models.CharField(
        max_length=20,
        choices=ReservationStatus.choices,
        default=ReservationStatus.PENDING,
    )
    payment_url = models.URLField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    celery_task_id = models.CharField(
        max_length=50, blank=True, null=True, verbose_name="شناسه تسک سلری"
    )
    find_train_number = models.CharField(
        _("شماره قطار پیدا شده"), blank=True, null=True, max_length=10, default=0
    )
    captcha_token = models.CharField(max_length=512, blank=True, null=True)

    class Meta:
        db_table = "reservation_attempts"
        verbose_name = _("درخواست های رزور")
        verbose_name_plural = _("درخواست های رزرو")


class Restitution(TimestampMixin, SoftDeleteMixin):
    serial_number = models.CharField(_("سریال بلیط"), max_length=255)
    phone = models.CharField(_("شماره موبایل"), max_length=15)
    train_number = models.CharField(_("شماره قطار"), max_length=10)
    hall_number = models.CharField(_("شماره سالن"), max_length=50)
    status = models.CharField(
        _("وضعیت"),
        max_length=10,
        choices=RestitutionEnum.choices,
        default=RestitutionEnum.PENDING,
        db_default=RestitutionEnum.PENDING,
    )
    error_message = models.TextField(_("خطای اختمالی"), blank=True, null=True)
    raja_account = models.ForeignKey(
        # TODO, when clean migration remove this blank and null
        RajaAccount,
        on_delete=models.CASCADE,
        verbose_name="اکانت رجا",
        blank=True,
        null=True,
    )
    task_id = models.CharField(
        _("ایدی تسک سلری"), max_length=100, blank=True, null=True
    )

    def clean(self):
        if not self.raja_account:
            raise ValidationError(_("تعریف اکانت رجا الزامی هست"))

    class Meta:
        db_table = "restitutions"
        verbose_name = _("استراد")
        verbose_name_plural = _("استرداد بلیط ها")
