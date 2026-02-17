"""
Admin configuration for Document and DocumentChunk models.
"""

from django.contrib import admin, messages
from django.utils.html import format_html

from apps.documents.models import Document, DocumentChunk


class EmbeddingStatusFilter(admin.SimpleListFilter):
    title = 'embedding status'
    parameter_name = 'embedding_status'

    def lookups(self, request, model_admin):
        return (
            ('complete', 'Complete (all chunks have embeddings)'),
            ('partial', 'Partial (some chunks missing embeddings)'),
            ('none', 'None (no embeddings)'),
            ('no_chunks', 'No chunks'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'complete':
            # Documents where all chunks have embeddings
            return queryset.filter(
                chunks__isnull=False
            ).exclude(
                chunks__embedding__isnull=True
            ).distinct()
        elif self.value() == 'partial':
            # Documents with some chunks having embeddings and some not
            return queryset.filter(
                chunks__embedding__isnull=False
            ).filter(
                chunks__embedding__isnull=True
            ).distinct()
        elif self.value() == 'none':
            # Documents where no chunks have embeddings
            return queryset.filter(
                chunks__isnull=False,
                chunks__embedding__isnull=True
            ).exclude(
                chunks__embedding__isnull=False
            ).distinct()
        elif self.value() == 'no_chunks':
            # Documents with no chunks at all
            return queryset.filter(chunks__isnull=True)


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
        "embedding_status",
        "created_by",
        "created_at",
    )
    list_filter = ("status", "is_active", "organization", "created_at", EmbeddingStatusFilter)
    search_fields = ("title", "organization__name")
    readonly_fields = (
        "id",
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
    actions = ["reprocess_documents", "generate_embeddings_for_documents"]

    def chunk_count(self, obj):
        return obj.chunk_count
    chunk_count.short_description = "Chunks"

    def embedding_status(self, obj):
        """Show embedding status for the document."""
        total_chunks = obj.chunks.count()
        if total_chunks == 0:
            return "No chunks"

        chunks_with_embeddings = obj.chunks.filter(embedding__isnull=False).count()

        if chunks_with_embeddings == 0:
            return f"⚬ 0/{total_chunks}"
        elif chunks_with_embeddings == total_chunks:
            return f"✓ {total_chunks}/{total_chunks}"
        else:
            return f"⚬ {chunks_with_embeddings}/{total_chunks}"

    embedding_status.short_description = "Embeddings"

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
        # post_save signal auto-triggers processing when status=PENDING + file exists

        if "file" in form.changed_data and obj.file:
            messages.info(
                request,
                f"Re-processing document '{obj.title}' because the file was updated.",
            )

    @admin.action(description="Reprocess selected documents (extract + chunk + embed)")
    def reprocess_documents(self, request, queryset):
        """Reprocess documents from scratch (text extraction + chunking + embeddings)."""
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

    @admin.action(description="Generate embeddings for selected documents")
    def generate_embeddings_for_documents(self, request, queryset):
        """Trigger embedding generation for documents that have chunks but missing embeddings."""
        from apps.documents.tasks import generate_embeddings_for_document

        scheduled_count = 0
        already_have_embeddings = 0
        no_chunks = 0
        failed_count = 0

        for document in queryset:
            # Check if document has chunks
            total_chunks = document.chunks.count()
            if total_chunks == 0:
                no_chunks += 1
                continue

            # Check if chunks need embeddings
            chunks_without_embeddings = document.chunks.filter(embedding__isnull=True).count()

            if chunks_without_embeddings == 0:
                already_have_embeddings += 1
                continue

            # Schedule embedding generation
            try:
                generate_embeddings_for_document.delay(str(document.id))
                scheduled_count += 1
                messages.info(
                    request,
                    f'Scheduled embedding generation for "{document.title}" '
                    f'({chunks_without_embeddings}/{total_chunks} chunks need embeddings)'
                )
            except Exception as e:
                failed_count += 1
                messages.error(
                    request,
                    f'Failed to schedule embeddings for "{document.title}": {e}'
                )

        # Summary message
        if scheduled_count > 0:
            messages.success(
                request,
                f"Successfully scheduled embedding generation for {scheduled_count} documents"
            )

        if already_have_embeddings > 0:
            messages.info(
                request,
                f"{already_have_embeddings} documents already have embeddings for all chunks"
            )

        if no_chunks > 0:
            messages.warning(
                request,
                f"{no_chunks} documents have no chunks (need processing first)"
            )

        if failed_count > 0:
            messages.error(
                request,
                f"Failed to schedule embeddings for {failed_count} documents"
            )


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = (
        "document_title",
        "chunk_index",
        "organization",
        "content_preview",
        "content_length",
        "embedding_status",
        "created_at",
    )
    list_filter = ("organization", "document__status", "created_at", "document")
    search_fields = ("content", "document__title", "organization__name")
    readonly_fields = ("id", "document", "organization", "chunk_index", "created_at", "updated_at")
    ordering = ["document", "chunk_index"]
    list_per_page = 25
    list_max_show_all = 100
    actions = ["generate_embeddings_for_selected"]

    fieldsets = (
        (
            "Chunk Info",
            {"fields": ("id", "document", "organization", "chunk_index")},
        ),
        (
            "Content",
            {"fields": ("content",)},
        ),
        (
            "Vector Embedding",
            {"fields": ("embedding",), "classes": ("collapse",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at")},
        ),
    )

    def document_title(self, obj):
        return obj.document.title
    document_title.short_description = "Document"
    document_title.admin_order_field = "document__title"

    def content_preview(self, obj):
        """Show formatted preview of the content with line breaks preserved"""
        content = obj.content[:150].replace('\n', ' | ')
        return content + "..." if len(obj.content) > 150 else content
    content_preview.short_description = "Content Preview"

    def content_length(self, obj):
        return len(obj.content)
    content_length.short_description = "Length"

    def embedding_status(self, obj):
        if obj.embedding is not None:
            return "✓ Has Embedding"
        else:
            return "⚬ No Embedding"
    embedding_status.short_description = "Embedding Status"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('document', 'organization')

    def get_readonly_fields(self, request, obj=None):
        # Make content editable for superusers only
        readonly = list(self.readonly_fields)
        if obj and not request.user.is_superuser:
            readonly.append('content')
        return readonly

    @admin.action(description="Generate embeddings for selected chunks")
    def generate_embeddings_for_selected(self, request, queryset):
        # Group chunks by document to generate embeddings efficiently
        documents_to_process = set()
        chunks_without_embeddings = 0

        for chunk in queryset:
            if chunk.embedding is None:
                documents_to_process.add(chunk.document)
                chunks_without_embeddings += 1

        if chunks_without_embeddings == 0:
            self.message_user(request, "All selected chunks already have embeddings.", level='WARNING')
            return

        # Schedule embedding generation for each document that has chunks needing embeddings
        from apps.documents.tasks import generate_embeddings_for_document
        scheduled_count = 0

        for document in documents_to_process:
            try:
                generate_embeddings_for_document.delay(str(document.id))
                scheduled_count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Failed to schedule embedding generation for {document.title}: {e}",
                    level='ERROR'
                )

        self.message_user(
            request,
            f"Scheduled embedding generation for {scheduled_count} documents "
            f"({chunks_without_embeddings} chunks without embeddings)",
            level='SUCCESS'
        )
