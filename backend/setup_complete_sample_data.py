#!/usr/bin/env python3
"""
Setup script — creates Arbisoft org, superuser, loads PDF, processes it (chunks + embeddings).
"""
import os
import secrets
import sys

import django

sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from django.core.files import File

from apps.core.models import Organization, User
from apps.documents.models import Document
from apps.documents.services.document_processor import process_document


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_PATH = os.path.join(REPO_ROOT, 'Arbisoft - FAQ.pdf')


def setup():
    print('=== Setting up sample data ===')

    # Superuser
    if not User.objects.filter(is_superuser=True).exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
        print('Superuser created: admin / admin123')
    else:
        print('Superuser already exists')

    # Organization
    org, created = Organization.objects.get_or_create(
        slug='arbisoft',
        defaults={
            'name': 'Arbisoft',
            'is_active': True,
            'api_key': f'pk_{secrets.token_urlsafe(32)}',
        }
    )
    print(f'Organization: {org.name} ({"created" if created else "exists"})')

    # Load PDF
    if not os.path.isfile(PDF_PATH):
        print(f'PDF not found at {PDF_PATH} — skipping document load')
        return

    doc, doc_created = Document.objects.get_or_create(
        title='Arbisoft - FAQ',
        organization=org,
        defaults={
            'status': Document.Status.PROCESSING,  # skip post_save auto-schedule
            'is_active': True,
            'category': Document.Category.POLICY,
        }
    )

    if doc_created or not doc.file:
        with open(PDF_PATH, 'rb') as f:
            doc.file.save('Arbisoft - FAQ.pdf', File(f), save=True)
        print(f'PDF attached to document: {doc.title}')
    else:
        print(f'Document already has file: {doc.title}')

    # Process: extract text → chunk → embed
    if doc.status != Document.Status.COMPLETED or doc.chunks.count() == 0:
        print('Processing document (extract → chunk → embed)...')
        result = process_document(doc)
        print(f'  Chunks: {result["chunks_created"]}')
        print(f'  Embeddings: {result["embeddings_generated"]}')
        print(f'  Text length: {result["text_length"]} chars')
    else:
        print(f'Document already processed ({doc.chunks.count()} chunks)')

    # Summary
    print(f'\n=== Done ===')
    print(f'  Documents: {Document.objects.filter(is_active=True).count()}')
    print(f'  Chunks: {doc.chunks.count()}')
    print(f'  Embeddings: {doc.chunks.filter(embedding__isnull=False).count()}')
    print(f'  Admin: http://127.0.0.1:8000/admin/ (admin / admin123)')


if __name__ == '__main__':
    setup()

    # Start Django dev server
    print('\n🌐 Starting Django dev server at http://127.0.0.1:8000 ...')
    from django.core.management import call_command
    call_command('runserver', '127.0.0.1:8000')

