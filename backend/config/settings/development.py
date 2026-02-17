"""
Development settings for policy-chatbot project.
"""

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ['*']

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
            'level': 'DEBUG',
            'handlers': ['console'],
            'propagate': False,
        },
    },
}
