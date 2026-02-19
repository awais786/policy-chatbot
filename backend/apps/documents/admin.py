"""
Simple Django admin interface for document management.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Document, DocumentChunk


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'organization', 'status', 'is_active', 'chunk_count', 'created_at']
    list_filter = ['status', 'is_active', 'organization', 'created_at']
    search_fields = ['title', 'organization__name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'processed_at', 'chunk_count']
    actions = ['reprocess_documents', 'reprocess_with_enhanced_pipeline']

    def reprocess_documents(self, request, queryset):
        """Admin action to reprocess selected documents."""
        count = 0
        for document in queryset:
            if document.file:
                document.status = Document.Status.PENDING
                document.error_message = ""
                document.save(update_fields=['status', 'error_message'])
                document.schedule_processing()
                count += 1

        self.message_user(request, f"Scheduled reprocessing for {count} documents.")
    reprocess_documents.short_description = "Reprocess selected documents"

    def reprocess_with_enhanced_pipeline(self, request, queryset):
        """Admin action to reprocess documents with enhanced text processing pipeline."""
        from apps.documents.services.document_processor import DocumentProcessingError

        count = 0
        chunks_created = 0

        for document in queryset:
            if not document.text_content:
                continue

            try:
                # Use the unified document processor
                result = document.process_document(chunk_size=1000, chunk_overlap=200)

                chunks_created += result['chunks_created']
                count += 1

                # Update document status
                document.status = Document.Status.COMPLETED
                document.save(update_fields=['status'])

            except DocumentProcessingError as e:
                self.message_user(
                    request,
                    f"Failed to reprocess {document.title}: {str(e)}",
                    level='ERROR'
                )

        self.message_user(
            request,
            f"Enhanced reprocessing completed! {count} documents processed, {chunks_created} chunks created with enhanced metadata."
        )
    reprocess_with_enhanced_pipeline.short_description = "Reprocess with enhanced text processing (preprocessing + sections + spaCy)"


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ['document', 'chunk_index', 'content_preview', 'has_embedding', 'organization']
    list_filter = ['document__organization', 'document__status']
    search_fields = ['document__title', 'content']
    readonly_fields = ['document', 'organization', 'chunk_index', 'created_at', 'updated_at']

    def content_preview(self, obj):
        """Show first 100 characters of chunk content."""
        if not obj.content:
            return "No content"
        preview = obj.content[:100].replace('\n', ' ')
        if len(obj.content) > 100:
            preview += "..."
        return preview
    content_preview.short_description = "Content Preview"

    def has_embedding(self, obj):
        """Show if chunk has embedding."""
        return obj.embedding is not None
    has_embedding.short_description = "Has Embedding"
    has_embedding.boolean = True
