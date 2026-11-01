from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Passenger, Order, Reservation


@admin.register(Passenger)
class PassengerAdmin(admin.ModelAdmin):
    list_per_page = 30
    list_display = (
        "id",
        "phone",
        "first_name",
        "last_name",
        "birth_date",
        "gender",
    )
    list_display_links = list_display
    search_fields = ("=phone",)
    search_help_text = _("برای جست و جو میتوانید از شماره تلفن کاربر استفاده کنید")


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
    list_display = ("id", "order_id", "raja_account_id", "status", "created_at")
    list_filter = ("status",)
    raw_id_fields = ("order", "raja_account")
    list_display_links = list_display
