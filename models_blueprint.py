"""
Django Models Blueprint for Policy Chatbot Application

This file contains the core data models for the multi-tenant 
document Q&A system with vector search capabilities.
"""

import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import ArrayField
from pgvector.django import VectorField
import hashlib
import secrets


class OrganizationManager(models.Manager):
    """Custom manager for Organization model"""
    
    def create_organization(self, name, slug=None):
        """Create organization with auto-generated API key"""
        if not slug:
            slug = name.lower().replace(' ', '-')
        
        api_key = f"pk_{secrets.token_urlsafe(32)}"
        
        return self.create(
            name=name,
            slug=slug,
            api_key=api_key
        )


class Organization(models.Model):
    """
    Multi-tenant organization model
    Each organization has isolated documents and conversations
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=255)
    
    # API authentication
    api_key = models.CharField(max_length=100, unique=True, db_index=True)
    api_key_hash = models.CharField(max_length=64, editable=False)  # SHA-256
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Configuration
    settings = models.JSONField(default=dict, blank=True)
    # Example settings structure:
    # {
    #     "widget": {
    #         "theme": "light",
    #         "primary_color": "#007bff",
    #         "position": "bottom-right"
    #     },
    #     "llm": {
    #         "provider": "openai",
    #         "model": "gpt-4-turbo",
    #         "temperature": 0.7,
    #         "max_tokens": 1000
    #     },
    #     "search": {
    #         "top_k": 5,
    #         "similarity_threshold": 0.7
    #     },
    #     "limits": {
    #         "max_documents": 1000,
    #         "max_queries_per_month": 10000
    #     }
    # }
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = OrganizationManager()
    
    class Meta:
        db_table = 'organizations'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['api_key']),
            models.Index(fields=['slug']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Hash API key before saving"""
        if self.api_key and not self.api_key_hash:
            self.api_key_hash = hashlib.sha256(
                self.api_key.encode()
            ).hexdigest()
        super().save(*args, **kwargs)
    
    def regenerate_api_key(self):
        """Generate new API key"""
        self.api_key = f"pk_{secrets.token_urlsafe(32)}"
        self.api_key_hash = hashlib.sha256(
            self.api_key.encode()
        ).hexdigest()
        self.save()
        return self.api_key


class User(AbstractUser):
    """
    Extended user model with organization relationship
    """
    
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True
    )
    
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('editor', 'Editor'),
        ('viewer', 'Viewer'),
    ]
    
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='viewer'
    )
    
    class Meta:
        db_table = 'users'
    
    def __str__(self):
        return f"{self.username} ({self.organization})"


class DocumentManager(models.Manager):
    """Custom manager for Document model"""
    
    def for_organization(self, organization):
        """Filter documents by organization"""
        return self.filter(organization=organization)
    
    def completed(self):
        """Get only completed documents"""
        return self.filter(status='completed')


class Document(models.Model):
    """
    Uploaded document model
    Represents a PDF file uploaded by an organization
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    
    # Document info
    title = models.CharField(max_length=500)
    file_path = models.CharField(max_length=1000)  # S3 key
    file_hash = models.CharField(max_length=64, db_index=True)  # SHA-256
    
    # Processing status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    error_message = models.TextField(blank=True, null=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    # Example metadata:
    # {
    #     "original_filename": "employee_handbook.pdf",
    #     "file_size": 1024000,
    #     "page_count": 50,
    #     "mime_type": "application/pdf",
    #     "uploaded_by": "user@example.com"
    # }
    
    # Relationships
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_documents'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    objects = DocumentManager()
    
    class Meta:
        db_table = 'documents'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['organization', 'created_at']),
            models.Index(fields=['file_hash']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'file_hash'],
                name='unique_document_per_org'
            )
        ]
    
    def __str__(self):
        return f"{self.title} ({self.organization})"
    
    @property
    def is_processed(self):
        return self.status == 'completed'
    
    @property
    def chunk_count(self):
        return self.chunks.count()


class DocumentChunkManager(models.Manager):
    """Custom manager for DocumentChunk model"""
    
    def for_organization(self, organization):
        """Filter chunks by organization"""
        return self.filter(organization=organization)
    
    def search_similar(self, organization, query_embedding, top_k=5, threshold=0.7):
        """
        Semantic search using pgvector
        
        Args:
            organization: Organization instance
            query_embedding: List/array of floats (embedding vector)
            top_k: Number of results to return
            threshold: Minimum similarity score (0-1)
        
        Returns:
            QuerySet of similar chunks ordered by relevance
        """
        from django.db.models import F
        from pgvector.django import CosineDistance
        
        # Using cosine distance (lower is better)
        # Convert to similarity: similarity = 1 - distance
        chunks = self.filter(
            organization=organization
        ).annotate(
            distance=CosineDistance('embedding', query_embedding)
        ).filter(
            distance__lt=(1 - threshold)  # Only get chunks above threshold
        ).order_by('distance')[:top_k]
        
        return chunks


class DocumentChunk(models.Model):
    """
    Text chunk with vector embedding
    Documents are split into chunks for semantic search
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships (denormalized for performance)
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='chunks'
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='chunks'
    )
    
    # Content
    content = models.TextField()
    
    # Vector embedding (dimension depends on model)
    # OpenAI text-embedding-3-small: 1536
    # all-MiniLM-L6-v2: 384
    embedding = VectorField(dimensions=1536)
    
    # Chunk metadata
    chunk_index = models.IntegerField()  # Order within document
    
    metadata = models.JSONField(default=dict, blank=True)
    # Example metadata:
    # {
    #     "page_number": 5,
    #     "section": "Benefits",
    #     "token_count": 250,
    #     "char_count": 1000
    # }
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = DocumentChunkManager()
    
    class Meta:
        db_table = 'document_chunks'
        ordering = ['document', 'chunk_index']
        indexes = [
            models.Index(fields=['organization', 'created_at']),
            models.Index(fields=['document', 'chunk_index']),
            # pgvector index created via migration:
            # CREATE INDEX ON document_chunks USING ivfflat (embedding vector_cosine_ops)
            # WITH (lists = 100);
        ]
    
    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document.title}"
    
    @property
    def preview(self):
        """Return first 100 characters"""
        return self.content[:100] + "..." if len(self.content) > 100 else self.content


class ConversationManager(models.Manager):
    """Custom manager for Conversation model"""
    
    def for_organization(self, organization):
        """Filter conversations by organization"""
        return self.filter(organization=organization)
    
    def for_session(self, session_id):
        """Get conversation by session ID"""
        return self.filter(session_id=session_id).first()


class Conversation(models.Model):
    """
    Chat conversation between user and assistant
    Tracks multiple messages in a session
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='conversations'
    )
    
    # Session tracking
    session_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    
    # User identification (optional, for analytics)
    user_identifier = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Email, user ID, or anonymous identifier"
    )
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    # Example metadata:
    # {
    #     "user_agent": "Mozilla/5.0...",
    #     "ip_address": "192.168.1.1",
    #     "referrer": "https://example.com/page"
    # }
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = ConversationManager()
    
    class Meta:
        db_table = 'conversations'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['organization', 'created_at']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        return f"Conversation {self.session_id} ({self.organization})"
    
    @property
    def message_count(self):
        return self.messages.count()
    
    @property
    def total_tokens(self):
        return self.messages.aggregate(
            models.Sum('tokens_used')
        )['tokens_used__sum'] or 0


class Message(models.Model):
    """
    Individual message in a conversation
    Can be from user, assistant, or system
    """
    
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    
    # Message content
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    
    # Source documents (for assistant messages)
    sources = models.JSONField(default=list, blank=True)
    # Example sources:
    # [
    #     {
    #         "document_id": "uuid",
    #         "document_title": "Employee Handbook",
    #         "chunk_id": "uuid",
    #         "chunk_preview": "Benefits include...",
    #         "page_number": 5,
    #         "similarity_score": 0.92
    #     }
    # ]
    
    # Token usage (for cost tracking)
    tokens_used = models.IntegerField(default=0)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    # Example metadata:
    # {
    #     "model": "gpt-4-turbo",
    #     "temperature": 0.7,
    #     "processing_time_ms": 1500,
    #     "cached": false
    # }
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'messages'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
        ]
    
    def __str__(self):
        preview = self.content[:50]
        return f"{self.role}: {preview}..."


class UsageLog(models.Model):
    """
    Track API usage for billing and analytics
    """
    
    EVENT_TYPES = [
        ('document_upload', 'Document Upload'),
        ('document_process', 'Document Processing'),
        ('query', 'Query'),
        ('embedding_generation', 'Embedding Generation'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='usage_logs'
    )
    
    # Event details
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    
    # Resource usage
    tokens_used = models.IntegerField(default=0)
    credits_used = models.DecimalField(max_digits=10, decimal_places=4, default=0)
    
    # References
    document = models.ForeignKey(
        Document,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Additional data
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'usage_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'event_type', 'created_at']),
            models.Index(fields=['organization', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.organization} - {self.event_type} ({self.tokens_used} tokens)"


# ============================================================================
# Model Utilities and Helper Functions
# ============================================================================

def get_organization_from_api_key(api_key):
    """
    Retrieve organization by API key
    
    Args:
        api_key: Plain text API key
    
    Returns:
        Organization instance or None
    """
    try:
        return Organization.objects.get(
            api_key=api_key,
            is_active=True
        )
    except Organization.DoesNotExist:
        return None


def log_usage(organization, event_type, **kwargs):
    """
    Log usage event
    
    Args:
        organization: Organization instance
        event_type: Type of event
        **kwargs: Additional fields (tokens_used, document, etc.)
    """
    UsageLog.objects.create(
        organization=organization,
        event_type=event_type,
        **kwargs
    )


def get_organization_stats(organization, start_date=None, end_date=None):
    """
    Get usage statistics for organization
    
    Args:
        organization: Organization instance
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
    
    Returns:
        Dictionary with statistics
    """
    from django.db.models import Count, Sum
    from django.utils import timezone
    from datetime import timedelta
    
    if not start_date:
        start_date = timezone.now() - timedelta(days=30)
    if not end_date:
        end_date = timezone.now()
    
    # Document stats
    document_count = Document.objects.for_organization(organization).count()
    completed_documents = Document.objects.for_organization(
        organization
    ).completed().count()
    
    # Conversation stats
    conversations = Conversation.objects.for_organization(
        organization
    ).filter(
        created_at__gte=start_date,
        created_at__lte=end_date
    )
    
    conversation_count = conversations.count()
    message_count = Message.objects.filter(
        conversation__in=conversations
    ).count()
    
    # Token usage
    total_tokens = Message.objects.filter(
        conversation__in=conversations
    ).aggregate(
        Sum('tokens_used')
    )['tokens_used__sum'] or 0
    
    # Usage logs
    usage_by_type = UsageLog.objects.filter(
        organization=organization,
        created_at__gte=start_date,
        created_at__lte=end_date
    ).values('event_type').annotate(
        count=Count('id'),
        total_tokens=Sum('tokens_used')
    )
    
    return {
        'organization': organization.name,
        'period': {
            'start': start_date,
            'end': end_date
        },
        'documents': {
            'total': document_count,
            'completed': completed_documents,
            'processing': document_count - completed_documents
        },
        'conversations': {
            'total': conversation_count,
            'messages': message_count,
            'avg_messages_per_conversation': (
                message_count / conversation_count if conversation_count > 0 else 0
            )
        },
        'tokens': {
            'total': total_tokens,
            'avg_per_message': (
                total_tokens / message_count if message_count > 0 else 0
            )
        },
        'usage_by_type': list(usage_by_type)
    }


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    """
    This section demonstrates how to use the models
    (Not meant to be executed directly - for reference only)
    """
    
    # Create organization
    org = Organization.objects.create_organization(
        name="Acme Corporation",
        slug="acme-corp"
    )
    print(f"Created org with API key: {org.api_key}")
    
    # Create user
    user = User.objects.create_user(
        username="john@acme.com",
        email="john@acme.com",
        password="secure_password",
        organization=org,
        role="admin"
    )
    
    # Create document
    document = Document.objects.create(
        organization=org,
        title="Employee Handbook 2024",
        file_path=f"{org.id}/documents/handbook.pdf",
        file_hash=hashlib.sha256(b"content").hexdigest(),
        created_by=user,
        metadata={
            "original_filename": "handbook.pdf",
            "file_size": 1024000,
            "page_count": 50
        }
    )
    
    # Create chunk with embedding
    chunk = DocumentChunk.objects.create(
        document=document,
        organization=org,
        content="Benefits include health insurance, 401k...",
        embedding=[0.1] * 1536,  # Dummy embedding
        chunk_index=0,
        metadata={
            "page_number": 5,
            "section": "Benefits"
        }
    )
    
    # Search similar chunks
    query_embedding = [0.1] * 1536  # Query embedding from user question
    similar_chunks = DocumentChunk.objects.search_similar(
        organization=org,
        query_embedding=query_embedding,
        top_k=5,
        threshold=0.7
    )
    
    # Create conversation
    conversation = Conversation.objects.create(
        organization=org,
        user_identifier="john@acme.com"
    )
    
    # Add messages
    Message.objects.create(
        conversation=conversation,
        role="user",
        content="What are the company benefits?",
        tokens_used=10
    )
    
    Message.objects.create(
        conversation=conversation,
        role="assistant",
        content="The company offers health insurance, 401k...",
        tokens_used=50,
        sources=[{
            "document_id": str(document.id),
            "document_title": document.title,
            "chunk_id": str(chunk.id),
            "page_number": 5
        }]
    )
    
    # Log usage
    log_usage(
        organization=org,
        event_type="query",
        tokens_used=60,
        conversation=conversation
    )
    
    # Get stats
    stats = get_organization_stats(org)
    print(f"Organization stats: {stats}")
