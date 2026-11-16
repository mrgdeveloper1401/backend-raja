import jdatetime
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    Passenger,
    Order,
    Reservation,
    ReservationAttempt,
    Restitution,
    OrderPassenger,
)


class OrderPassengerInline(admin.StackedInline):
    model = OrderPassenger
    extra = 1
    raw_id_fields = ("passenger",)


@admin.register(Passenger)
class PassengerAdmin(admin.ModelAdmin):
    list_per_page = 30
    list_display = (
        "id",
        "first_name",
        "last_name",
        "birth_date",
        "show_jdatetime",
        "is_adult",
        "created_at",
        "updated_at"
    )
    list_display_links = list_display

    def show_jdatetime(self, obj):
        return jdatetime.date.fromgregorian(
            year=obj.birth_date.year, month=obj.birth_date.month, day=obj.birth_date.day
        )

    show_jdatetime.short_description = _("تاریخ تولد شمسی")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_per_page = 30
    list_display = (
        "id",
        "origin",
        "destination",
        "travel_date",
        "created_at",
        "updated_at"
    )
    list_display_links = list_display
    ordering = ("-id",)
    inlines = (OrderPassengerInline,)


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_per_page = 30
    list_display = ("id", "order_id", "raja_account_id", "is_exclusive", "created_at", "updated_at")
    raw_id_fields = ("order", "raja_account")
    list_display_links = list_display
    list_filter = ("is_exclusive", "created_at")


@admin.register(ReservationAttempt)
class ReservationAttemptAdmin(admin.ModelAdmin):
    list_display = ("reservation_id", "id","status", "created_at", "updated_at")
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
        "raja_account_phone",
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
                "error_message",
            )
        )


@admin.register(OrderPassenger)
class OrderPassengerAdmin(admin.ModelAdmin):
    raw_id_fields = ("passenger", "order")
    list_display = ("id", "order_id", "passenger_id", "created_at")
    list_display_links = list_display
    list_per_page = 30
