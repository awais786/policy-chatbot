"""
Admin configuration for Document model.
"""

from django import forms
from django.contrib import admin
from django.utils.html import format_html
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone

import mimetypes

from apps.documents.models import Document
from apps.documents.services.storage import document_upload_path


class DocumentAdminForm(forms.ModelForm):
    class Meta:
        model = Document
        # Exclude computed/read-only fields from the editable form to avoid
        # validation errors — they are computed by the model during save.
        exclude = ('file_hash', 'metadata')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    form = DocumentAdminForm

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
    # Show file upload in admin; compute file_hash automatically in model.save
    readonly_fields = ("id", "file_hash", "created_at", "updated_at", "processed_at")
    fieldsets = (
        (
            "Document Info",
            {"fields": ("id", "title", "organization", "file", "created_by")},
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

    def save_model(self, request, obj, form, change):
        """Handle file upload from the admin 'upload_file' and persist via default_storage.

        This stores the file using Django's configured storage backend (local in dev).
        It computes SHA-256 for dedup/unique constraint, sets file_path and metadata,
        and saves the model instance.
        """

        # set created_by if missing
        if not obj.created_by and request.user and request.user.is_authenticated:
            obj.created_by = request.user

        super().save_model(request, obj, form, change)

    def file_preview(self, obj):
        # Prefer the FileField; fall back to stored name if present
        file_field = getattr(obj, 'file', None)
        if not file_field or not getattr(file_field, 'name', None):
            return "-"
        try:
            url = file_field.url
        except Exception:
            url = default_storage.url(file_field.name)
        return format_html('<a href="{}" target="_blank">Download</a>', url)

    file_preview.short_description = "File"
