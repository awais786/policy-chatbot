"""
Policy Chatbot - Project Setup and Structure Guide

This file outlines the complete project structure and setup commands
for the Django-based document Q&A application.
"""

# ============================================================================
# PROJECT STRUCTURE
# ============================================================================

PROJECT_STRUCTURE = """
policy-chatbot/
│
├── backend/                          # Django application
│   ├── config/                       # Django settings
│   │   ├── __init__.py
│   │   ├── settings/
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # Common settings
│   │   │   ├── development.py       # Dev settings
│   │   │   ├── production.py        # Prod settings
│   │   │   └── test.py              # Test settings
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   │
│   ├── apps/
│   │   ├── __init__.py
│   │   │
│   │   ├── core/                    # Core app (models, utilities)
│   │   │   ├── __init__.py
│   │   │   ├── models.py            # Organization, User
│   │   │   ├── admin.py
│   │   │   ├── managers.py
│   │   │   └── middleware.py        # API key auth middleware
│   │   │
│   │   ├── documents/               # Document management
│   │   │   ├── __init__.py
│   │   │   ├── models.py            # Document, DocumentChunk
│   │   │   ├── admin.py
│   │   │   ├── api/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── serializers.py
│   │   │   │   ├── views.py
│   │   │   │   └── urls.py
│   │   │   ├── tasks.py             # Celery tasks
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── pdf_extractor.py
│   │   │   │   ├── text_chunker.py
│   │   │   │   ├── embeddings.py
│   │   │   │   └── storage.py       # S3 integration
│   │   │   └── tests/
│   │   │       ├── test_models.py
│   │   │       ├── test_api.py
│   │   │       └── test_tasks.py
│   │   │
│   │   ├── conversations/           # Chat conversations
│   │   │   ├── __init__.py
│   │   │   ├── models.py            # Conversation, Message
│   │   │   ├── admin.py
│   │   │   ├── api/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── serializers.py
│   │   │   │   ├── views.py
│   │   │   │   └── urls.py
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── search.py        # Vector search
│   │   │   │   ├── llm.py           # LLM integration
│   │   │   │   └── prompts.py       # Prompt templates
│   │   │   └── tests/
│   │   │
│   │   ├── widget/                  # Widget API
│   │   │   ├── __init__.py
│   │   │   ├── api/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── views.py
│   │   │   │   └── urls.py
│   │   │   └── templates/
│   │   │       └── widget/
│   │   │           └── demo.html
│   │   │
│   │   └── analytics/               # Usage tracking
│   │       ├── __init__.py
│   │       ├── models.py            # UsageLog
│   │       ├── admin.py
│   │       └── services/
│   │           ├── __init__.py
│   │           └── stats.py
│   │
│   ├── requirements/
│   │   ├── base.txt                 # Common dependencies
│   │   ├── development.txt
│   │   ├── production.txt
│   │   └── test.txt
│   │
│   ├── manage.py
│   ├── pytest.ini
│   └── .env.example
│
├── widget/                          # JavaScript widget
│   ├── src/
│   │   ├── index.js
│   │   ├── api/
│   │   │   └── client.js
│   │   ├── components/
│   │   │   ├── ChatWidget.js
│   │   │   ├── MessageList.js
│   │   │   ├── MessageInput.js
│   │   │   └── SourceCard.js
│   │   ├── styles/
│   │   │   ├── main.css
│   │   │   └── themes.css
│   │   └── utils/
│   │       ├── markdown.js
│   │       └── storage.js
│   ├── dist/                        # Build output
│   ├── package.json
│   ├── webpack.config.js
│   └── README.md
│
├── infrastructure/                  # AWS infrastructure as code
│   ├── terraform/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   ├── modules/
│   │   │   ├── vpc/
│   │   │   ├── ecs/
│   │   │   ├── rds/
│   │   │   ├── s3/
│   │   │   └── cloudfront/
│   │   └── environments/
│   │       ├── dev/
│   │       ├── staging/
│   │       └── production/
│   │
│   └── docker/
│       ├── Dockerfile
│       ├── Dockerfile.celery
│       ├── docker-compose.yml
│       └── docker-compose.prod.yml
│
├── docs/                            # Documentation
│   ├── api/
│   │   ├── authentication.md
│   │   ├── documents.md
│   │   └── query.md
│   ├── deployment/
│   │   ├── aws.md
│   │   ├── docker.md
│   │   └── local.md
│   ├── guides/
│   │   ├── getting-started.md
│   │   ├── widget-integration.md
│   │   └── customization.md
│   └── architecture.md
│
├── examples/                        # Example integrations
│   ├── react-app/
│   ├── vanilla-js/
│   └── python-client/
│
├── scripts/                         # Utility scripts
│   ├── setup_pgvector.sh
│   ├── generate_api_key.py
│   ├── backup_db.sh
│   └── load_sample_data.py
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       ├── deploy-staging.yml
│       └── deploy-production.yml
│
├── .gitignore
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
└── CHANGELOG.md
"""

# ============================================================================
# DEPENDENCIES
# ============================================================================

BASE_REQUIREMENTS = """
# Django and Extensions
Django==5.0.1
djangorestframework==3.14.0
django-cors-headers==4.3.1
# django-environ removed — use runtime environment variables instead
django-extensions==3.2.3
django-filter==23.5

# Database
psycopg2-binary==2.9.9
pgvector==0.2.5

# Celery and Redis
celery==5.3.4
redis==5.0.1
django-celery-beat==2.5.0
django-celery-results==2.5.1

# AWS
boto3==1.34.34
django-storages==1.14.2

# Document Processing
PyPDF2==3.0.1
pdfplumber==0.10.4
python-magic==0.4.27

# Text Processing and Embeddings
langchain==0.1.4
langchain-openai==0.0.5
tiktoken==0.5.2
sentence-transformers==2.3.1

# LLM Providers
openai==1.10.0
anthropic==0.8.1

# Authentication and Security
pyjwt==2.8.0
cryptography==42.0.1

# API Documentation
drf-spectacular==0.27.0

# Utilities
requests==2.31.0
python-dateutil==2.8.2
pytz==2024.1
"""

DEVELOPMENT_REQUIREMENTS = """
-r base.txt

# Testing
pytest==7.4.4
pytest-django==4.7.0
pytest-cov==4.1.0
pytest-mock==3.12.0
factory-boy==3.3.0
faker==22.2.0

# Code Quality
black==24.1.1
flake8==7.0.0
isort==5.13.2
pylint==3.0.3
mypy==1.8.0
django-stubs==4.2.7

# Debugging
ipython==8.20.0
django-debug-toolbar==4.2.0
"""

PRODUCTION_REQUIREMENTS = """
-r base.txt

# Production Server
gunicorn==21.2.0
whitenoise==6.6.0

# Monitoring
sentry-sdk==1.39.2
django-prometheus==2.3.1

# Performance
django-redis==5.4.0
"""

# ============================================================================
# DJANGO SETTINGS STRUCTURE
# ============================================================================

DJANGO_BASE_SETTINGS = '''
"""
Base Django settings for policy-chatbot project.
"""

import os
from pathlib import Path

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# No built-in .env loader: environment variables must be provided by the runtime.
# Use direct os.environ lookups below.

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')

# DEBUG flag (truthy values: 1,true,yes,on)
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('1', 'true', 'yes', 'on')

# ALLOWED_HOSTS (comma-separated list)
ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h.strip()]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party
    'rest_framework',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'django_celery_beat',
    'django_celery_results',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.APIKeyAuthMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'OPTIONS': {
            'options': '-c search_path=public'
        }
    }
}

# Custom user model
AUTH_USER_MODEL = 'core.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (S3)
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', '')
AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', default='us-east-1')
AWS_DEFAULT_ACL = None
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}

# Celery Configuration
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes

# Cache Configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', default='redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
    }
}

# CORS Settings
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [h.strip() for h in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',') if h.strip()]
CORS_ALLOW_CREDENTIALS = True

# Application Settings
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', default='')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', default='')

# Document Processing Settings
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_DOCUMENT_TYPES = ['application/pdf']
CHUNK_SIZE = 1000  # tokens
CHUNK_OVERLAP = 200  # tokens
EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL', default='text-embedding-3-small')
EMBEDDING_DIMENSIONS = 1536

# LLM Settings
DEFAULT_LLM_PROVIDER = os.environ.get('DEFAULT_LLM_PROVIDER', default='openai')
DEFAULT_LLM_MODEL = os.environ.get('DEFAULT_LLM_MODEL', default='gpt-4-turbo-preview')
DEFAULT_LLM_TEMPERATURE = 0.7
DEFAULT_LLM_MAX_TOKENS = 1000

# Search Settings
DEFAULT_TOP_K = 5
DEFAULT_SIMILARITY_THRESHOLD = 0.7

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
'''

# ============================================================================
# SETUP COMMANDS
# ============================================================================

SETUP_COMMANDS = {
    "1. Install Python and PostgreSQL": """
    # macOS
    brew install python@3.11 postgresql@15
    
    # Ubuntu
    sudo apt update
    sudo apt install python3.11 python3.11-venv postgresql-15
    """,
    
    "2. Install pgvector extension": """
    # macOS
    brew install pgvector
    
    # Ubuntu
    sudo apt install postgresql-15-pgvector
    
    # Or build from source
    cd /tmp
    git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
    cd pgvector
    make
    sudo make install
    """,
    
    "3. Create PostgreSQL database": """
    # Create database and user
    psql postgres
    CREATE DATABASE policy_chatbot;
    CREATE USER policy_user WITH PASSWORD 'secure_password';
    ALTER ROLE policy_user SET client_encoding TO 'utf8';
    ALTER ROLE policy_user SET default_transaction_isolation TO 'read committed';
    ALTER ROLE policy_user SET timezone TO 'UTC';
    GRANT ALL PRIVILEGES ON DATABASE policy_chatbot TO policy_user;
    
    # Enable pgvector extension
    \\c policy_chatbot
    CREATE EXTENSION IF NOT EXISTS vector;
    \\q
    """,
    
    "4. Create Python virtual environment": """
    python3.11 -m venv venv
    source venv/bin/activate  # On Windows: venv\\Scripts\\activate
    pip install --upgrade pip setuptools wheel
    """,
    
    "5. Install dependencies": """
    pip install -r backend/requirements/development.txt
    """,
    
    "6. Create environment file": """
    cp backend/.env.example backend/.env
    # Edit .env with your settings
    """,
    
    "7. Run Django migrations": """
    cd backend
    python manage.py makemigrations
    python manage.py migrate
    """,
    
    "8. Create pgvector index": """
    python manage.py dbshell
    
    -- Create IVFFlat index for faster similarity search
    CREATE INDEX ON document_chunks 
    USING ivfflat (embedding vector_cosine_ops) 
    WITH (lists = 100);
    
    -- Create HNSW index (better performance, more memory)
    -- CREATE INDEX ON document_chunks 
    -- USING hnsw (embedding vector_cosine_ops);
    """,
    
    "9. Create superuser": """
    python manage.py createsuperuser
    """,
    
    "10. Run development server": """
    # Terminal 1: Django
    python manage.py runserver
    
    # Terminal 2: Celery worker
    celery -A config worker -l info
    
    # Terminal 3: Celery beat (scheduler)
    celery -A config beat -l info
    
    # Terminal 4: Redis
    redis-server
    """
}

# ============================================================================
# CELERY CONFIGURATION
# ============================================================================

CELERY_CONFIG = '''
"""
Celery configuration for policy-chatbot project.
"""

import os
from celery import Celery
from django.conf import settings

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')

app = Celery('policy_chatbot')

# Load config from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing"""
    print(f'Request: {self.request!r}')
'''

# ============================================================================
# DOCKER CONFIGURATION
# ============================================================================

DOCKERFILE = '''
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    postgresql-client \\
    libpq-dev \\
    libmagic1 \\
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements/production.txt .
RUN pip install --no-cache-dir -r production.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Run gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "config.wsgi:application"]
'''

DOCKER_COMPOSE = '''
version: '3.9'

services:
  db:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_DB: policy_chatbot
      POSTGRES_USER: policy_user
      POSTGRES_PASSWORD: policy_pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    environment:
      - DEBUG=1
      - DB_HOST=db
      - DB_NAME=policy_chatbot
      - DB_USER=policy_user
      - DB_PASSWORD=policy_pass
      - CELERY_BROKER_URL=redis://redis:6379/0
      - REDIS_URL=redis://redis:6379/1
    depends_on:
      - db
      - redis
  
  celery_worker:
    build: .
    command: celery -A config worker -l info
    volumes:
      - .:/app
    environment:
      - DEBUG=1
      - DB_HOST=db
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
  
  celery_beat:
    build: .
    command: celery -A config beat -l info
    volumes:
      - .:/app
    environment:
      - DEBUG=1
      - DB_HOST=db
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

volumes:
  postgres_data:
'''

# ============================================================================
# EXAMPLE API USAGE
# ============================================================================

API_USAGE_EXAMPLES = '''
"""
API Usage Examples for Policy Chatbot
"""

import requests
import json

# Base configuration
BASE_URL = "http://localhost:8000"
API_KEY = "pk_your_api_key_here"
HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}


def upload_document(file_path):
    """Upload a PDF document"""
    url = f"{BASE_URL}/api/v1/documents/upload/"
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        headers = {"X-API-Key": API_KEY}  # No Content-Type for multipart
        
        response = requests.post(url, headers=headers, files=files)
        return response.json()


def check_document_status(document_id):
    """Check processing status of a document"""
    url = f"{BASE_URL}/api/v1/documents/{document_id}/status/"
    response = requests.get(url, headers=HEADERS)
    return response.json()


def list_documents():
    """List all documents"""
    url = f"{BASE_URL}/api/v1/documents/"
    response = requests.get(url, headers=HEADERS)
    return response.json()


def query_documents(question, conversation_id=None):
    """Ask a question about documents"""
    url = f"{BASE_URL}/api/v1/query/"
    
    payload = {
        "question": question,
        "conversation_id": conversation_id  # Optional, for follow-up questions
    }
    
    response = requests.post(url, headers=HEADERS, json=payload)
    return response.json()


def semantic_search(query, top_k=5):
    """Perform semantic search without LLM"""
    url = f"{BASE_URL}/api/v1/search/"
    
    payload = {
        "query": query,
        "top_k": top_k
    }
    
    response = requests.post(url, headers=HEADERS, json=payload)
    return response.json()


def get_conversation_history(conversation_id):
    """Retrieve conversation history"""
    url = f"{BASE_URL}/api/v1/conversations/{conversation_id}/messages/"
    response = requests.get(url, headers=HEADERS)
    return response.json()


# Example workflow
if __name__ == "__main__":
    # 1. Upload a document
    print("Uploading document...")
    result = upload_document("employee_handbook.pdf")
    document_id = result['id']
    print(f"Document uploaded: {document_id}")
    
    # 2. Check processing status
    import time
    while True:
        status = check_document_status(document_id)
        print(f"Status: {status['status']}")
        
        if status['status'] == 'completed':
            break
        elif status['status'] == 'failed':
            print(f"Error: {status['error_message']}")
            exit(1)
        
        time.sleep(5)
    
    # 3. Query the documents
    print("\\nQuerying documents...")
    response = query_documents("What are the company benefits?")
    
    print(f"Answer: {response['answer']}")
    print(f"\\nSources:")
    for source in response['sources']:
        print(f"  - {source['document_title']} (page {source['page_number']})")
    
    conversation_id = response['conversation_id']
    
    # 4. Follow-up question
    print("\\nAsking follow-up question...")
    response = query_documents(
        "How do I enroll?",
        conversation_id=conversation_id
    )
    print(f"Answer: {response['answer']}")
    
    # 5. Get conversation history
    print("\\nConversation history:")
    history = get_conversation_history(conversation_id)
    for message in history['messages']:
        print(f"{message['role'].upper()}: {message['content'][:100]}...")
'''

# ============================================================================
# WIDGET INTEGRATION EXAMPLE
# ============================================================================

WIDGET_EXAMPLE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Policy Chatbot Widget Example</title>
</head>
<body>
    <h1>Your Website Content</h1>
    <p>The chatbot widget will appear in the bottom-right corner.</p>
    
    <!-- Load the widget -->
    <script 
        src="https://cdn.yourapp.com/widget-v1.0.0.js"
        data-api-key="pk_your_api_key_here"
        data-theme="light"
        data-primary-color="#007bff"
        data-position="bottom-right"
    ></script>
    
    <!-- Advanced initialization (optional) -->
    <script>
        // Wait for widget to load
        window.addEventListener('PolicyChatbotLoaded', function() {
            // Get widget instance
            const chatbot = window.PolicyChatbot;
            
            // Customize further
            chatbot.configure({
                welcomeMessage: "Hi! Ask me anything about our policies.",
                placeholder: "Type your question...",
                maxHeight: "600px",
                showSourceLinks: true,
                allowFileUpload: false
            });
            
            // Listen to events
            chatbot.on('message-sent', function(data) {
                console.log('User sent:', data.message);
            });
            
            chatbot.on('message-received', function(data) {
                console.log('Bot replied:', data.message);
            });
            
            // Programmatically open/close
            // chatbot.open();
            // chatbot.close();
            
            // Send message programmatically
            // chatbot.sendMessage("What are the benefits?");
        });
    </script>
</body>
</html>
'''

# ============================================================================
# TESTING EXAMPLES
# ============================================================================

TEST_EXAMPLES = '''
"""
Example tests for Policy Chatbot
"""

import pytest
from django.test import TestCase
from apps.core.models import Organization, User
from apps.documents.models import Document, DocumentChunk
from apps.conversations.services.search import semantic_search
from apps.documents.services.text_chunker import chunk_text


class OrganizationTestCase(TestCase):
    """Test Organization model"""
    
    def test_create_organization(self):
        """Test creating organization with API key"""
        org = Organization.objects.create_organization(
            name="Test Corp",
            slug="test-corp"
        )
        
        self.assertEqual(org.name, "Test Corp")
        self.assertTrue(org.api_key.startswith("pk_"))
        self.assertIsNotNone(org.api_key_hash)
    
    def test_regenerate_api_key(self):
        """Test API key regeneration"""
        org = Organization.objects.create_organization(name="Test Corp")
        old_key = org.api_key
        
        new_key = org.regenerate_api_key()
        
        self.assertNotEqual(old_key, new_key)
        self.assertTrue(new_key.startswith("pk_"))


@pytest.mark.django_db
class TestDocumentProcessing:
    """Test document processing pipeline"""
    
    def test_chunk_text(self):
        """Test text chunking"""
        text = "This is a test. " * 500  # Long text
        chunks = chunk_text(text, chunk_size=1000, overlap=200)
        
        assert len(chunks) > 1
        assert all(len(chunk) <= 1500 for chunk in chunks)  # Approximate
    
    def test_semantic_search(self, organization, sample_chunks):
        """Test semantic search"""
        query = "employee benefits"
        results = semantic_search(
            organization=organization,
            query=query,
            top_k=5
        )
        
        assert len(results) <= 5
        assert all(hasattr(r, 'content') for r in results)
        assert all(hasattr(r, 'similarity_score') for r in results)


@pytest.fixture
def organization():
    """Create test organization"""
    return Organization.objects.create_organization(name="Test Corp")


@pytest.fixture
def sample_chunks(organization):
    """Create sample document chunks"""
    doc = Document.objects.create(
        organization=organization,
        title="Test Doc",
        file_path="test.pdf",
        file_hash="abc123",
        status="completed"
    )
    
    chunks = []
    for i in range(10):
        chunk = DocumentChunk.objects.create(
            document=doc,
            organization=organization,
            content=f"Test content about benefits {i}",
            embedding=[0.1] * 1536,  # Dummy embedding
            chunk_index=i
        )
        chunks.append(chunk)
    
    return chunks
'''

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    """
    This script can be used to generate project scaffolding
    """
    
    print("=" * 80)
    print("POLICY CHATBOT - PROJECT SETUP GUIDE")
    print("=" * 80)
    print()
    print("Project Structure:")
    print(PROJECT_STRUCTURE)
    print()
    print("=" * 80)
    print("SETUP COMMANDS")
    print("=" * 80)
    
    for step, commands in SETUP_COMMANDS.items():
        print(f"\\n{step}")
        print("-" * 40)
        print(commands.strip())
    
    print()
    print("=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("""
    1. Follow the setup commands above
    2. Review the IMPLEMENTATION_PLAN.md for detailed architecture
    3. Review models_blueprint.py for database schema
    4. Start with Phase 1: Core Backend
    5. Implement document upload and storage
    6. Build the processing pipeline
    7. Add search and query functionality
    8. Develop the widget
    9. Deploy to AWS
    
    For detailed implementation guidance, see IMPLEMENTATION_PLAN.md
    """)
