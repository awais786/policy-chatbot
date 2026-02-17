"""
Admin configuration for Document model.
"""

from django.contrib import admin
from django.utils.html import format_html

from apps.documents.models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "organization",
        "status",
        "is_active",
        "created_by",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "is_active", "organization", "created_at")
    search_fields = ("title", "organization__name")
    readonly_fields = (
        "id",
        "file_hash",
        "created_at",
        "updated_at",
        "processed_at",
    )
    fieldsets = (
        (
            "Document Info",
            {"fields": ("id", "title", "organization", "file", "created_by")},
        ),
        (
            "Status & Settings",
            {"fields": ("status", "is_active", "error_message", "processed_at")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at")},
        ),
    )

    def file_preview(self, obj):
        if obj.file and obj.file.name:
            return format_html(
                '<a href="{}" target="_blank">Download</a>', obj.file.url
            )
        return "-"

    file_preview.short_description = "File"

    def save_model(self, request, obj, form, change):
        if not obj.created_by and request.user and request.user.is_authenticated:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
