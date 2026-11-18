from django.contrib import admin

from .models import Station, RajaApiKey


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "english_name",
        "tel_code",
        "group",
        "is_car_ticket",
        "is_exclusion",
    )
    list_display_links = list_display


@admin.register(RajaApiKey)
class RajaApiKeyAdmin(admin.ModelAdmin):
    list_display = ("id", "api_key", "created_at", "updated_at")
    list_display_links = ("id", "api_key")
