"""
Admin configuration for core models (Organization, User).
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.core.models import Organization, User, Website


class WebsiteInline(admin.TabularInline):
    model = Website
    extra = 1
    fields = ("domain", "name", "url", "is_primary", "is_active")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """Admin interface for Organization model."""

    list_display = ("name", "slug", "is_active", "created_at", "updated_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "slug")
    readonly_fields = ("id", "api_key_hash", "created_at", "updated_at")
    prepopulated_fields = {"slug": ("name",)}

    inlines = [WebsiteInline]

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


@admin.register(Website)
class WebsiteAdmin(admin.ModelAdmin):
    """Admin interface for Website model."""

    list_display = ("domain", "organization", "is_primary", "is_active", "created_at")
    list_filter = ("is_primary", "is_active", "organization")
    search_fields = ("domain", "organization__name")
    readonly_fields = ("id", "created_at", "updated_at")
    fieldsets = (
        ("Website Info", {"fields": ("id", "organization", "name", "domain", "url")}),
        ("Settings", {"fields": ("is_primary", "is_active")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
