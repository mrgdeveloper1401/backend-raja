from django.contrib import admin

from .models import Passenger, Order


@admin.register(Passenger)
class PassengerAdmin(admin.ModelAdmin):
    list_per_page = 30
    raw_id_fields = ("user",)
    list_display = (
        "id",
        "user_id",
        "phone",
        "first_name",
        "last_name",
        "birth_date",
        "gender",
    )
    list_display_links = list_display


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_per_page = 30
    raw_id_fields = ("passenger",)
    list_display = (
        "id",
        "passenger_id",
        "origin",
        "destination",
        "travel_date",
    )
    list_display_links = list_display
    ordering = ("-id",)
