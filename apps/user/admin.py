from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User, RajaAccount


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("id",)
    list_display = (
        "id",
        "phone",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "created_at",
        "updated_at",
    )
    list_display_links = list_display
    search_fields = ("=phone",)
    search_help_text = _("برای جست و جو میتوانید از شماره موبایل استفاده کنید")

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "phone",
                    "email",
                    "usable_password",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
    readonly_fields = ("last_login", "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        (
            _("Personal info"),
            {"fields": ("first_name", "last_name", "email", "username")},
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "created_at", "updated_at")}),
    )


@admin.register(RajaAccount)
class RajaAccountAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "username",
        "password",
        "is_active",
        "created_at",
        "updated_at",
    )
    list_display_links = list_display
