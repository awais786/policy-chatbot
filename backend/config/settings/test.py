"""
Test settings for policy-chatbot project.
"""

from .base import *  # noqa: F401, F403

DEBUG = False

# Faster password hashing for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# In-memory cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Disable throttling in tests
REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = []  # noqa: F405
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {}  # noqa: F405

# Use local filesystem storage instead of S3
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
MEDIA_ROOT = BASE_DIR / 'test_media'  # noqa: F405
