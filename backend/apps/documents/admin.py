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
        "created_by",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "organization", "created_at")
    search_fields = ("title", "organization__name")
    readonly_fields = (
        "id",
        "file_hash",
        "file_preview",
        "created_at",
        "updated_at",
        "processed_at",
    )
    fieldsets = (
        ("Document Info", {"fields": ("id", "title", "organization", "created_by")}),
        ("File Details", {"fields": ("file", "file_hash", "file_preview", "metadata")}),
        ("Processing", {"fields": ("status", "error_message", "processed_at")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    def file_preview(self, obj):
        if obj.file:
            return format_html(
                '<a href="{}" target="_blank">Download</a>', obj.file.url
            )
        return "-"

    file_preview.short_description = "File"
