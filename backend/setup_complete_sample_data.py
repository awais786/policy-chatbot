#!/usr/bin/env python3
"""
Complete sample data setup script - creates documents, chunks, and embeddings
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from apps.core.models import Organization, User
from apps.documents.models import Document, DocumentChunk
from apps.documents.services.embeddings import generate_embeddings

def simple_chunk_text(text, chunk_size=500):
    """Simple text chunking by sentences"""
    if not text or not text.strip():
        return []

    sentences = []
    for sent in text.replace('\n', ' ').split('.'):
        sent = sent.strip()
        if sent:
            sentences.append(sent + '.')

    chunks = []
    current_chunk = ''

    for sentence in sentences:
        if len(current_chunk + sentence) <= chunk_size:
            current_chunk += ' ' + sentence if current_chunk else sentence
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks

def setup_complete_sample_data():
    print('🎯 Creating complete sample data for Policy Chatbot...')

    # Step 0: Create organization and superuser
    print('\n🏢 Step 0: Creating organization and superuser...')

    org, created = Organization.objects.get_or_create(
        name='Sample Organization',
        defaults={'slug': 'sample-org', 'is_active': True}
    )
    print(f'✅ Organization: {org.name} (created: {created})')

    if not User.objects.filter(is_superuser=True).exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
        print('✅ Superuser created: admin/admin123')
    else:
        print('✅ Superuser already exists')

    # Sample documents
    documents_data = [
        {
            'title': 'Company Policy Manual',
            'text_content': '''Company Policy Manual - Employee Handbook

Working Hours: Our standard working hours are Monday to Friday, 9:00 AM to 5:00 PM. 
Employees are expected to maintain punctuality and regular attendance.

Leave Policy:
- Annual Leave: 21 days per year
- Sick Leave: 10 days per year  
- Maternity/Paternity Leave: 12 weeks paid leave
- Emergency Leave: 3 days per year for family emergencies

Remote Work Policy: Employees may work remotely up to 2 days per week with manager approval.
Remote work requests must be submitted at least 48 hours in advance.

Benefits Package:
- Health insurance coverage for employee and family
- 401(k) retirement plan with company matching
- Professional development budget: 2000 dollars per year'''
        },
        {
            'title': 'IT Security Guidelines',
            'text_content': '''IT Security Guidelines - Information Technology Security Policy

Password Requirements:
- Minimum 12 characters with uppercase, lowercase, numbers, and symbols
- Passwords must be changed every 90 days
- Two-factor authentication is mandatory for all systems

Data Protection:
- All sensitive data must be encrypted when stored or transmitted
- USB drives and external storage devices require approval
- Personal devices cannot access company data without proper security software

Network Access:
- VPN is required for all remote connections
- Guest network access requires IT approval
- Unauthorized software installation is prohibited'''
        },
        {
            'title': 'Travel and Expense Policy',
            'text_content': '''Travel and Expense Policy - Business Travel Guidelines

Travel Authorization: All business travel must be pre-approved by department manager.
Travel requests should be submitted at least 2 weeks in advance.

Accommodation:
- Hotel stays should not exceed 200 dollars per night in major cities
- 150 dollars per night limit in smaller cities

Meals and Entertainment:
- Meal allowance: 75 dollars per day for domestic travel
- 100 dollars per day for international travel
- Receipts required for all expenses over 25 dollars

Transportation:
- Economy class flights for domestic travel under 6 hours
- Business class allowed for international flights over 8 hours'''
        }
    ]

    print('\n📄 Step 1: Creating sample documents...')
    for doc_data in documents_data:
        document, created = Document.objects.get_or_create(
            title=doc_data['title'],
            organization=org,
            defaults={
                'text_content': doc_data['text_content'],
                'status': Document.Status.COMPLETED,
                'is_active': True
            }
        )

        if created:
            print(f'  ✅ Created: {document.title}')
        else:
            print(f'  ✅ Already exists: {document.title}')

    print('\n🔄 Step 2: Generate chunks for documents...')

    # Process documents to create chunks
    documents = Document.objects.filter(text_content__isnull=False, is_active=True).exclude(text_content='')
    chunks_created = 0

    for doc in documents:
        existing_chunks = DocumentChunk.objects.filter(document=doc).count()
        if existing_chunks > 0:
            print(f'  ✅ {doc.title} already has {existing_chunks} chunks')
            continue

        chunks = simple_chunk_text(doc.text_content)
        for i, chunk_content in enumerate(chunks):
            DocumentChunk.objects.create(
                document=doc,
                organization=doc.organization,
                chunk_index=i,
                content=chunk_content
            )
            chunks_created += 1

        print(f'  📦 Created {len(chunks)} chunks for {doc.title}')

    print(f'📝 Total new chunks created: {chunks_created}')

    print('\n🔄 Step 3: Generate embeddings for all chunks...')

    # Generate embeddings for chunks without them
    chunks_without_embeddings = DocumentChunk.objects.filter(embedding__isnull=True)
    embeddings_created = 0

    for chunk in chunks_without_embeddings:
        try:
            embeddings = generate_embeddings([chunk.content])
            if embeddings and len(embeddings) > 0:
                chunk.embedding = embeddings[0]
                chunk.save()
                embeddings_created += 1
                print(f'  ✅ {chunk.document.title} - Chunk {chunk.chunk_index}')
        except Exception as e:
            print(f'  ❌ Error with {chunk.document.title} - Chunk {chunk.chunk_index}: {e}')

    print(f'🧠 Total embeddings created: {embeddings_created}')

    # Final summary
    total_docs = Document.objects.filter(is_active=True).count()
    total_chunks = DocumentChunk.objects.count()
    total_embeddings = DocumentChunk.objects.filter(embedding__isnull=False).count()

    print('\n🎉 Complete sample data setup finished!')
    print(f'📊 Summary:')
    print(f'  📄 Documents: {total_docs}')
    print(f'  📝 Chunks: {total_chunks}')
    print(f'  🧠 Embeddings: {total_embeddings}')

    if total_embeddings == total_chunks:
        print('\n✅ All chunks have embeddings! Ready for testing.')
        print('  - Test search: make test-search')
        print('  - Test chat: make test-chat')
    else:
        print(f'\n⚠️  {total_chunks - total_embeddings} chunks missing embeddings')

if __name__ == '__main__':
    setup_complete_sample_data()
