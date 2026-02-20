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
SECRET_KEY = "aaa"

# DEBUG flag (truthy values: 1,true,yes,on)
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('1', 'true', 'yes', 'on')

# ALLOWED_HOSTS (comma-separated list)
ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h.strip()]

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
]

LOCAL_APPS = [
    'apps.core',
    'apps.documents',
    'apps.chatbot',
    'apps.widget',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Database — PostgreSQL with pgvector
# ---------------------------------------------------------------------------

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'OPTIONS': {
            'options': '-c search_path=public',
        },
    }
}

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

AUTH_USER_MODEL = 'core.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ---------------------------------------------------------------------------
# Media / S3 storage
# ---------------------------------------------------------------------------

DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', '')
AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
AWS_DEFAULT_ACL = None
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}

# ---------------------------------------------------------------------------
# Cache — Redis
# ---------------------------------------------------------------------------

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
    }
}

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------

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
    },
}

# ---------------------------------------------------------------------------
# drf-spectacular
# ---------------------------------------------------------------------------

SPECTACULAR_SETTINGS = {
    'TITLE': 'Policy Chatbot API',
    'DESCRIPTION': 'Multi-tenant document Q&A system with RAG.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

CORS_ALLOW_ALL_ORIGINS = True  # Allow all origins for development
CORS_ALLOWED_ORIGINS = [h.strip() for h in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',') if h.strip()]
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# LLM provider keys
# ---------------------------------------------------------------------------

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

# ---------------------------------------------------------------------------
# Document processing
# ---------------------------------------------------------------------------

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
ALLOWED_DOCUMENT_TYPES = ['application/pdf']
CHUNK_SIZE = 500   # characters — smaller chunks keep contact details together
CHUNK_OVERLAP = 100  # characters

# ---------------------------------------------------------------------------
# Embedding provider — "ollama" (local) or "openai" (cloud)
# ---------------------------------------------------------------------------

EMBEDDING_PROVIDER = os.environ.get('EMBEDDING_PROVIDER', 'openai')

# OpenAI settings (used when EMBEDDING_PROVIDER = "openai")
EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL', 'text-embedding-3-small')
EMBEDDING_DIMENSIONS = int(os.environ.get('EMBEDDING_DIMENSIONS', '1536'))

# Ollama settings (used when EMBEDDING_PROVIDER = "ollama")
OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_EMBEDDING_MODEL = os.environ.get('OLLAMA_EMBEDDING_MODEL', 'nomic-embed-text')

# ---------------------------------------------------------------------------
# LLM defaults
# ---------------------------------------------------------------------------

DEFAULT_LLM_PROVIDER = os.environ.get('DEFAULT_LLM_PROVIDER', 'openai')
DEFAULT_LLM_MODEL = os.environ.get('DEFAULT_LLM_MODEL', 'gpt-4-turbo-preview')
DEFAULT_LLM_TEMPERATURE = 0.7
DEFAULT_LLM_MAX_TOKENS = 1000

# ---------------------------------------------------------------------------
# Default organization — resolved dynamically from DB when not provided.
# Set DEFAULT_ORGANIZATION_SLUG to auto-resolve by slug if needed.
# ---------------------------------------------------------------------------

DEFAULT_ORGANIZATION_SLUG = os.environ.get('DEFAULT_ORGANIZATION_SLUG', 'arbisoft')

# ---------------------------------------------------------------------------
# Search defaults
# ---------------------------------------------------------------------------

DEFAULT_TOP_K = 10
DEFAULT_SIMILARITY_THRESHOLD = 0.3

# ---------------------------------------------------------------------------
# Chatbot (RAG) defaults
# ---------------------------------------------------------------------------

CHATBOT_LLM_PROVIDER = os.environ.get("CHATBOT_LLM_PROVIDER", "ollama")
CHATBOT_LLM_MODEL = os.environ.get("CHATBOT_LLM_MODEL", "mistral")
CHATBOT_ENABLE_CHAT_HISTORY = os.environ.get(
    "CHATBOT_ENABLE_CHAT_HISTORY", "true"
).lower() in ("1", "true", "yes", "on")
CHATBOT_MAX_CONTEXT_CHARS = int(os.environ.get("CHATBOT_MAX_CONTEXT_CHARS", "8000"))

# ---------------------------------------------------------------------------
# Celery — async task queue
# ---------------------------------------------------------------------------

CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 600  # 10 minutes hard limit per task
CELERY_TASK_SOFT_TIME_LIMIT = 540  # 9 minutes soft limit

# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
