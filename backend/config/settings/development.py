"""
Development settings for policy-chatbot project.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ['*']

# ---------------------------------------------------------------------------
# Database — SQLite for local development
# ---------------------------------------------------------------------------

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  # noqa: F405
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
# Celery — run tasks synchronously in development (no worker needed)
# ---------------------------------------------------------------------------

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# ---------------------------------------------------------------------------
# Embeddings — use local Ollama in development (free, no API key needed)
# Run: ollama pull nomic-embed-text
# ---------------------------------------------------------------------------

EMBEDDING_PROVIDER = 'ollama'
OLLAMA_BASE_URL = 'http://localhost:11434'
OLLAMA_EMBEDDING_MODEL = 'nomic-embed-text'
EMBEDDING_DIMENSIONS = 768  # nomic-embed-text outputs 768-dim vectors

