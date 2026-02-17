"""
Django management command to generate embeddings for documents that don't have them.
"""

from django.core.management.base import BaseCommand
from django.db.models import Q, Count

from apps.documents.models import Document, DocumentChunk
from apps.documents.tasks import generate_embeddings_for_document


class Command(BaseCommand):
    help = 'Generate embeddings for documents that have chunks but no embeddings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--document-id',
            type=str,
            help='Generate embeddings for a specific document ID (optional)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force regeneration of embeddings even if they already exist',
        )

    def handle(self, *args, **options):
        if options['document_id']:
            # Generate embeddings for specific document
            self.process_single_document(options['document_id'], options['dry_run'], options.get('force', False))
        else:
            # Default behavior: process all documents that need embeddings
            self.process_all_documents(options['dry_run'], options.get('force', False))

    def process_single_document(self, document_id, dry_run, force=False):
        try:
            document = Document.objects.get(pk=document_id)
        except Document.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Document {document_id} not found")
            )
            return

        total_chunks = document.chunks.count()
        if total_chunks == 0:
            self.stdout.write(
                self.style.WARNING(f"Document '{document.title}' has no chunks to process")
            )
            return

        chunks_without_embeddings = document.chunks.filter(embedding__isnull=True).count()
        chunks_with_embeddings = total_chunks - chunks_without_embeddings

        self.stdout.write(
            f"Document: {document.title}\n"
            f"  Total chunks: {total_chunks}\n"
            f"  Chunks with embeddings: {chunks_with_embeddings}\n"
            f"  Chunks without embeddings: {chunks_without_embeddings}"
        )

        # Determine if we need to process this document
        should_process = False
        if force:
            should_process = True
            self.stdout.write("  Force mode: Will regenerate all embeddings")
        elif chunks_without_embeddings > 0:
            should_process = True
            self.stdout.write(f"  Will generate embeddings for {chunks_without_embeddings} chunks")
        else:
            self.stdout.write(
                self.style.SUCCESS("  All chunks already have embeddings")
            )

        if should_process:
            if dry_run:
                self.stdout.write(
                    self.style.WARNING("[DRY RUN] Would schedule embedding generation")
                )
            else:
                # Clear existing embeddings if force mode
                if force:
                    document.chunks.update(embedding=None)
                    self.stdout.write("  Cleared existing embeddings (force mode)")

                # Schedule embedding generation
                try:
                    result = generate_embeddings_for_document.delay(str(document.id))
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Scheduled embedding generation (task: {result.id})"
                        )
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  Failed to schedule embedding generation: {e}")
                    )

    def process_all_documents(self, dry_run, force=False):
        # Find documents that have chunks
        if force:
            # If force mode, process all documents that have chunks
            documents_to_process = Document.objects.filter(
                status=Document.Status.COMPLETED,
                chunks__isnull=False
            ).distinct().order_by('created_at')
            action_desc = "regenerate embeddings for all"
        else:
            # Normal mode: only process documents with missing embeddings
            documents_to_process = Document.objects.filter(
                status=Document.Status.COMPLETED,
                chunks__embedding__isnull=True
            ).distinct().order_by('created_at')
            action_desc = "generate missing embeddings for"

        if not documents_to_process.exists():
            if force:
                self.stdout.write(
                    self.style.WARNING("No completed documents with chunks found!")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS("All documents already have embeddings!")
                )
            return

        self.stdout.write(f"Found {documents_to_process.count()} documents to {action_desc}:")

        scheduled_count = 0
        total_chunks_to_process = 0

        for document in documents_to_process:
            total_chunks = document.chunks.count()

            if force:
                chunks_needing_embeddings = total_chunks
            else:
                chunks_needing_embeddings = document.chunks.filter(embedding__isnull=True).count()

            total_chunks_to_process += chunks_needing_embeddings

            if chunks_needing_embeddings > 0 or force:
                self.stdout.write(
                    f"  - {document.title} ({chunks_needing_embeddings}/{total_chunks} chunks)"
                )

                if not dry_run:
                    try:
                        # Clear existing embeddings if force mode
                        if force:
                            document.chunks.update(embedding=None)

                        generate_embeddings_for_document.delay(str(document.id))
                        scheduled_count += 1
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"    Failed to schedule: {e}")
                        )

        # Summary
        self.stdout.write("\n" + "="*50)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] Would {action_desc} {documents_to_process.count()} documents\n"
                    f"Total chunks to process: {total_chunks_to_process}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully scheduled embedding generation for {scheduled_count} documents\n"
                    f"Total chunks to process: {total_chunks_to_process}"
                )
            )
