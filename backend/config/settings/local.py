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

# Use Hugging Face for local development (no server required, runs offline)
EMBEDDING_PROVIDER = 'huggingface'
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384  # all-MiniLM-L6-v2 generates 384-dimensional vectors


# Alternative: Use Ollama (requires running ollama serve)
# EMBEDDING_PROVIDER = 'ollama'
# OLLAMA_BASE_URL = 'http://localhost:11434'
# OLLAMA_EMBEDDING_MODEL = 'nomic-embed-text'
# EMBEDDING_DIMENSIONS = 768

# Alternative: Use OpenAI (requires API key)
# EMBEDDING_PROVIDER = 'openai'
# OPENAI_API_KEY = 'your-openai-api-key-here'

# ---------------------------------------------------------------------------
# Chatbot Configuration
# ---------------------------------------------------------------------------

# LLM Provider Settings
CHATBOT_LLM_PROVIDER = 'ollama'  # or 'openai'
CHATBOT_LLM_MODEL = 'mistral'    # Model name for the LLM provider

# Chat History Settings
CHATBOT_ENABLE_CHAT_HISTORY = True
CHATBOT_CHAT_HISTORY_RECENT_MESSAGES = 6

# Context and Response Settings
CHATBOT_MAX_CONTEXT_CHARS = 8000  # Maximum characters in context sent to LLM
CHATBOT_MAX_SEARCH_RESULTS = 5    # Number of search results to include in context

# Prompt Templates
CHATBOT_PROMPT_TEMPLATE = """You are a knowledgeable assistant helping users find information from documents. Your goal is to provide accurate, helpful answers based strictly on the provided context.

**Instructions:**
1. Answer ONLY using information explicitly stated in the context below
2. If the context contains the answer, provide a clear, well-structured response
3. Cite the source document when providing information (e.g., "According to [Document Title]...")
4. If the context does NOT contain enough information to answer the question, respond with: "I don't have enough information in the available content to answer that question."
5. Be concise but complete - prioritize clarity over brevity
6. If the question has multiple parts, address each part separately
7. Do not make assumptions or add information not present in the context

**Context:**
{context}

**Question:**
{question}

**Answer:**"""

CHATBOT_SYSTEM_PROMPT = """You are a knowledgeable assistant for document search. Answer questions using ONLY the provided context. Always cite sources when available. If you cannot answer based on the context, clearly state "I don't have enough information to answer that question." Be accurate, concise, and helpful."""
