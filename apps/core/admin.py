from django.contrib import admin
from django.db.models import JSONField
from django_json_widget.widgets import JSONEditorWidget

from .models import Station, RajaApiKey, RajaConfig


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
    raw_id_fields = ("raja_account",)


@admin.register(RajaConfig)
class RajaConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "updated_at")
    formfield_overrides = {
        JSONField: {"widget": JSONEditorWidget},
    }
    list_display_links = list_display
