import jdatetime
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Passenger, Order, Reservation, ReservationAttempt, Restitution


@admin.register(Passenger)
class PassengerAdmin(admin.ModelAdmin):
    list_per_page = 30
    list_display = (
        "id",
        "phone",
        "first_name",
        "last_name",
        "birth_date",
        "show_jdatetime",
        "gender",
    )
    list_display_links = list_display
    search_fields = ("=phone",)
    search_help_text = _("برای جست و جو میتوانید از شماره تلفن کاربر استفاده کنید")

    def show_jdatetime(self, obj):
        return jdatetime.date.fromgregorian(
            year=obj.birth_date.year, month=obj.birth_date.month, day=obj.birth_date.day
        )

    show_jdatetime.short_description = _("تاریخ تولد شمسی")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_per_page = 30
    raw_id_fields = ("passenger",)
    list_display = (
        "id",
        "passenger_id",
        "get_phone",
        "origin",
        "destination",
        "travel_date",
    )
    list_display_links = list_display
    ordering = ("-id",)
    list_select_related = ("passenger",)
    search_fields = ("=passenger__phone",)
    search_help_text = _("برای جست و جو میتوانید از شماره تماس مسافر استفاده کنید")

    def get_phone(self, obj):
        return obj.passenger.phone

    get_phone.short_description = "شماره تلفن مسافر"

    def get_queryset(self, request):
        fields = (
            "passenger__phone",
            "origin",
            "destination",
            "travel_date",
            "passenger_type",
        )
        return super().get_queryset(request).only(*fields)


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_per_page = 30
    list_display = ("id", "order_id", "raja_account_id", "created_at")
    raw_id_fields = ("order", "raja_account")
    list_display_links = list_display


@admin.register(ReservationAttempt)
class ReservationAttemptAdmin(admin.ModelAdmin):
    list_display = ("reservation_id", "status", "created_at", "updated_at")
    list_display_links = list_display
    list_per_page = 20
    list_filter = ("created_at",)
    raw_id_fields = ("reservation",)


@admin.register(Restitution)
class RestitutionAdmin(admin.ModelAdmin):
    list_display = (
        "serial_number",
        "phone",
        "train_number",
        "hall_number",
        "created_at",
        "status",
        "raja_account_id",
        "raja_account_phone"
    )
    list_display_links = list_display
    list_per_page = 20
    list_filter = ("status", "created_at")
    search_fields = ("=serial_number",)
    search_help_text = _("برای جست و جو میتوانید از سریال نمابر استفاده کنید")
    list_select_related = ("raja_account",)
    raw_id_fields = ("raja_account",)

    def raja_account_phone(self, obj):
        return obj.raja_account.username

    raja_account_phone.short_description = _("اکانت رجا")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .only(
                "serial_number",
                "phone",
                "train_number",
                "hall_number",
                "created_at",
                "status",
                "raja_account__username",
                "updated_at",
                'error_message'
            )
        )
