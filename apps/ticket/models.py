from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import TimestampMixin, SoftDeleteMixin
from django.utils.translation import gettext_lazy as _

from apps.user.models import RajaAccount


class ReservationStatus(models.TextChoices):
    WAITING_START = "waiting_start", _("در انتظار شروع")
    PENDING = "pending", _("انتظار")
    MONITORING = "monitoring", _("در حال رصد")
    REDIRECT_GATEWAY = "redirect_gateway", _("هدایت به درگاه پرداخت")
    FAILED = "failed", _("ناموفق")
    CAPTCHA = "captcha", _("حل کپچا")
    MATCH_TRAIN = "match_train", _("قطارهای یافت شده")


class RestitutionEnum(models.TextChoices):
    SUCCESS = "success", _("موفق")
    FAILED = "failed", _("ناموفق")
    PENDING = "pending", _("انتظار")


class DepartureTimeSlot(models.IntegerChoices):
    H00_06 = 0, _("۰۰ تا ۰۶")
    H06_12 = 6, _("۰۶ تا ۱۲")
    H12_18 = 12, _("۱۲ تا ۱۸")
    H18_21 = 18, _("۱۸ تا ۲۱")
    H21_24 = 21, _("۲۱ تا ۲۴")


class Passenger(TimestampMixin, SoftDeleteMixin):
    class Gender(models.TextChoices):
        MALE = "male", "مرد"
        FEMALE = "female", "زن"

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    national_id = models.CharField(max_length=10)
    birth_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def is_adult(self):
        """
        بررسی می‌کند که آیا مسافر ۱۲ سال به بالا هست یا خیر.
        اگر تاریخ تولد ثبت نشده باشد، به صورت پیش‌فرض بزرگسال در نظر گرفته می‌شود.
        """
        if not self.birth_date:
            return True  # یا False، بسته به منطق کسب و کار شما (معمولاً بزرگسال در نظر می‌گیرند)

        today = timezone.now().date()

        # محاسبه سن دقیق
        age = today.year - self.birth_date.year

        # اگر هنوز به ماه تولد نرسیده یا در همان ماه به روز تولد نرسیده، یک سال از سن کم می‌کنیم
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            age -= 1

        return age >= 12

    class Meta:
        db_table = "passengers"
        verbose_name = _("مسافر")
        verbose_name_plural = _("مسافران")


class Order(TimestampMixin, SoftDeleteMixin):
    class PassengerType(models.TextChoices):
        MAN = "male", _("ویژه برادران")
        WOMAN = "famale", _("ویژه خواهران")
        NORMAL = "family", _("مسافرین عادی")

    class TripType(models.TextChoices):
        OUT_BOUND = "outbound", _("تک سفر")
        OUT_BOUND_AND_RETURN = "outbound_and_return", _("مسیر رفت و برگشت")

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
        max_length=7,
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


class OrderPassenger(SoftDeleteMixin, TimestampMixin):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="order_passenger"
    )
    passenger = models.ForeignKey(
        Passenger, on_delete=models.CASCADE, related_name="passenger_order"
    )

    class Meta:
        db_table = "order_passenger"
        verbose_name = _("جدول مسافران و سفارش ها")
        verbose_name_plural = _("جدول مسافران و سفارش ها")
        constraints = [
            models.UniqueConstraint(
                fields=["order", "passenger"],
                condition=models.Q(is_deleted=False)
                | models.Q(is_deleted__isnull=True),
                name="uniq_active_order_passenger",
            )
        ]


class Reservation(TimestampMixin, SoftDeleteMixin):
    class CoupeType(models.TextChoices):
        ALL = "all", _("هر نوع کوه ای")
        FOUR = "four", _("4 تخته 4 ستاره")
        FOUR_FIVE = "four_five", _("4 تخته 5 ستاره")
        THREE = "three", _("سه ستاره 6 تخته")
        FIVE = "five", _("5 ستاره")
        SALON = "salon", _("سالنی")

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
        _("نوع کوپه"), max_length=9, blank=True, null=True, choices=CoupeType.choices
    )
    is_exclusive = models.BooleanField(_("کوپه دربست"), default=False, db_default=False)
    # زمان حرکت (قطار رفت)
    departure_time_slots = ArrayField(
        base_field=models.PositiveSmallIntegerField(
            choices=DepartureTimeSlot.choices,
        ),
        verbose_name=_("بازه‌های ساعت حرکت"),
        default=list,
        blank=True,
        help_text=_("بدون انتخاب، همهٔ ساعات مجاز هستند."),
    )

    from_price = models.DecimalField(
        blank=True, null=True, max_digits=10, decimal_places=2
    )
    to_price = models.DecimalField(
        blank=True, null=True, max_digits=10, decimal_places=2
    )
    train_number = ArrayField(
        default=list,
        blank=True,
        null=True,
        help_text=_("لیستی از شماره قطارهای مجاز برای رزرو"),
        base_field=models.CharField(max_length=10),
    )
    adult_number = models.PositiveSmallIntegerField(default=1, db_default=1)
    baby_number = models.PositiveSmallIntegerField(default=0, db_default=0)
    phone = models.CharField(
        _("شماره موبایل رزرو کننده"), max_length=15, blank=True, null=True
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
        default=ReservationStatus.WAITING_START,
        db_default=ReservationStatus.WAITING_START,
    )
    payment_url = models.URLField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    celery_task_id = models.CharField(
        max_length=50, blank=True, null=True, verbose_name="شناسه تسک سلری"
    )
    captcha_token = models.CharField(max_length=512, blank=True, null=True)
    user_agent = models.CharField(max_length=1024, null=True)
    accept_data = models.JSONField(blank=True, null=True)
    matching_trains = models.JSONField(blank=True, null=True)
    find_trains = models.JSONField(blank=True, null=True)

    class Meta:
        db_table = "reservation_attempts"
        verbose_name = _("درخواست های رزور")
        verbose_name_plural = _("درخواست های رزرو")
