from django.contrib import admin

from .models import Station


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
