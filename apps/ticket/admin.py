import jdatetime
from django.contrib import admin
from django.db.models import JSONField
from django.utils.translation import gettext_lazy as _
from django_json_widget.widgets import JSONEditorWidget

from .models import (
    Passenger,
    Order,
    Reservation,
    ReservationAttempt,
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
        "updated_at",
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
        "updated_at",
    )
    list_display_links = list_display
    ordering = ("-id",)
    inlines = (OrderPassengerInline,)


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_per_page = 30
    list_display = (
        "id",
        "order_id",
        "raja_account_id",
        "is_exclusive",
        "departure_time_slots",
        "from_price",
        "to_price",
        "train_number",
        "adult_number",
        "baby_number",
        "coupe_type",
    )
    raw_id_fields = ("order", "raja_account")
    list_display_links = list_display
    list_filter = ("is_exclusive", "coupe_type")
    formfield_overrides = {
        JSONField: {"widget": JSONEditorWidget},
    }


@admin.register(ReservationAttempt)
class ReservationAttemptAdmin(admin.ModelAdmin):
    list_display = ("reservation_id", "id", "status", "created_at", "updated_at")
    list_display_links = ("reservation_id", "id", "created_at", "updated_at")
    list_per_page = 20
    list_filter = ("created_at",)
    raw_id_fields = ("reservation",)
    formfield_overrides = {
        JSONField: {"widget": JSONEditorWidget},
    }
    list_editable = ("status",)


@admin.register(OrderPassenger)
class OrderPassengerAdmin(admin.ModelAdmin):
    raw_id_fields = ("passenger", "order")
    list_display = ("id", "order_id", "passenger_id", "created_at")
    list_display_links = list_display
    list_per_page = 30
