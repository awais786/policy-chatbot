"""
URL configuration for policy-chatbot project.
"""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # API v1
    path('api/v1/documents/', include('apps.documents.api.urls')),

    # Widget
    path('widget/', include('apps.widget.api.urls')),

    # API Schema & Docs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path(
        'api/schema/swagger/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui',
    ),
    path(
        'api/schema/redoc/',
        SpectacularRedocView.as_view(url_name='schema'),
        name='redoc',
    ),
]

# Include Django Debug Toolbar URLs when in DEBUG and debug_toolbar is installed
if settings.DEBUG:
    try:
        import debug_toolbar  # noqa: F401

        urlpatterns = [path('__debug__/', include('debug_toolbar.urls'))] + urlpatterns
    except Exception:
        # If debug_toolbar isn't available, skip including its URLs.
        pass

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
