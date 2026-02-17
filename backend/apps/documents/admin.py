"""
Admin configuration for Document and DocumentChunk models.
"""

from django.contrib import admin, messages
from django.utils.html import format_html

from apps.documents.models import Document, DocumentChunk


class DocumentChunkInline(admin.TabularInline):
    model = DocumentChunk
    fields = ("chunk_index", "content_preview", "has_embedding")
    readonly_fields = ("chunk_index", "content_preview", "has_embedding")
    extra = 0
    max_num = 0

    def content_preview(self, obj):
        return obj.content[:120] + "..." if len(obj.content) > 120 else obj.content
    content_preview.short_description = "Content"

    def has_embedding(self, obj):
        return obj.embedding is not None
    has_embedding.boolean = True
    has_embedding.short_description = "Embedded"


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "organization",
        "status",
        "is_active",
        "chunk_count",
        "created_by",
        "created_at",
    )
    list_filter = ("status", "is_active", "organization", "created_at")
    search_fields = ("title", "organization__name")
    readonly_fields = (
        "id",
        "file_hash",
        "text_content",
        "chunk_count",
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
            "Processing Info",
            {"fields": ("chunk_count",)},
        ),
        (
            "Extracted Content",
            {"fields": ("text_content",), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at")},
        ),
    )
    inlines = [DocumentChunkInline]
    actions = ["reprocess_documents"]

    def chunk_count(self, obj):
        return obj.chunk_count
    chunk_count.short_description = "Chunks"

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

        # Trigger async processing when a new file is uploaded via admin
        if "file" in form.changed_data:
            obj.schedule_processing()
            messages.info(
                request,
                f'Processing started for "{obj.title}". '
                "Text extraction and embeddings will be generated in the background.",
            )

    @admin.action(description="Reprocess selected documents (extract + chunk + embed)")
    def reprocess_documents(self, request, queryset):
        count = 0
        for doc in queryset:
            if doc.file:
                doc.status = Document.Status.PENDING
                doc.error_message = ""
                doc.save(update_fields=["status", "error_message", "updated_at"])
                doc.schedule_processing()
                count += 1

        messages.success(
            request,
            f"Reprocessing started for {count} document(s).",
        )
