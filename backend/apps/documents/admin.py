"""
Admin configuration for Document and DocumentChunk models.
"""

from django.contrib import admin

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
    readonly_fields = ("id", "file_hash", "created_at", "updated_at", "processed_at")
    fieldsets = (
        (
            "Document Info",
            {"fields": ("id", "title", "organization", "created_by")},
        ),
        (
            "File Details",
            {"fields": ("file_path", "file_hash", "metadata")},
        ),
        (
            "Processing",
            {"fields": ("status", "error_message", "processed_at")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at")},
        ),
    )
