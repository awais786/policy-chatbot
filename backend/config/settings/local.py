"""
Local settings for policy-chatbot project (development/local).

This file mirrors `development.py` but is named `local.py` so local
environments can explicitly use `config.settings.local`.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ['*']

# ---------------------------------------------------------------------------
# Database — PostgreSQL with pgvector for local development
# ---------------------------------------------------------------------------

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'chatbot_db',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'localhost',
        'PORT': '5432',
        'OPTIONS': {
            'options': '-c search_path=public',
        },
    }
}

# ---------------------------------------------------------------------------
# Debug toolbar
# ---------------------------------------------------------------------------

INSTALLED_APPS += ['debug_toolbar']  # noqa: F405

MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')  # noqa: F405

INTERNAL_IPS = ['127.0.0.1']

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ---------------------------------------------------------------------------
# Logging — show SQL queries
# ---------------------------------------------------------------------------

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django.db.backends': {
            'level': 'WARNING',
            'handlers': ['console'],
            'propagate': False,
        },
    },
}

# Media (local storage for development)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'  # noqa: F405

# Use local file system storage in development (override S3 default)
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# Ensure media root exists when settings are imported in development
import os
os.makedirs(str(MEDIA_ROOT), exist_ok=True)

# ---------------------------------------------------------------------------
# Celery Configuration for Local Development
# ---------------------------------------------------------------------------

# For local development, run tasks synchronously (no Redis required)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Or if you want async behavior locally, use Redis:
# CELERY_BROKER_URL = 'redis://localhost:6379/0'
# CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# ---------------------------------------------------------------------------
# Embedding Configuration for Local Development
# ---------------------------------------------------------------------------

# Use Ollama for local development (no API key required)
EMBEDDING_PROVIDER = 'ollama'

OLLAMA_BASE_URL = 'http://localhost:11434'
OLLAMA_EMBEDDING_MODEL = 'nomic-embed-text'
EMBEDDING_DIMENSIONS = 768

# If you prefer OpenAI for local development, uncomment these lines:
# EMBEDDING_PROVIDER = 'openai'
# OPENAI_API_KEY = 'your-openai-api-key-here'
