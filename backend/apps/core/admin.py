"""
Admin configuration for core models (Organization, User).
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.core.models import Organization, User


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """Admin interface for Organization model."""

    list_display = ("name", "slug", "is_active", "created_at", "updated_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "slug")
    readonly_fields = ("id", "api_key_hash", "created_at", "updated_at")
    prepopulated_fields = {"slug": ("name",)}

    fieldsets = (
        (
            "General Info",
            {
                "fields": ("id", "name", "slug"),
            },
        ),
        (
            "API Authentication",
            {
                "fields": ("api_key", "api_key_hash"),
            },
        ),
        (
            "Configuration",
            {
                "fields": ("settings", "is_active"),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for custom User model."""

    list_display = ("username", "email", "organization", "role", "is_active")
    list_filter = ("role", "is_active", "organization")

    # Extend default fieldsets with organization & role.
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Organization",
            {
                "fields": ("organization", "role"),
            },
        ),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "Organization",
            {
                "fields": ("organization", "role"),
            },
        ),
    )
