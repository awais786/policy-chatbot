"""
Custom middleware for the policy-chatbot project.

APIKeyAuthMiddleware — extracts organization from the X-API-Key header
and attaches it to the request.
"""

from django.http import JsonResponse

from apps.core.models import Organization


class APIKeyAuthMiddleware:
    """Authenticate requests via X-API-Key header.

    For every incoming request the middleware checks for an ``X-API-Key``
    header.  If present, it looks up the corresponding active Organization
    and attaches it as ``request.organization``.  Admin, docs, and health
    check paths are exempt so they work without a key.
    """

    EXEMPT_PREFIXES = (
        "/admin/",
        "/api/schema/",
        "/health/",
        "/api/v1/chat/health/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_exempt(request.path):
            request.organization = None
            return self.get_response(request)

        api_key = request.META.get("HTTP_X_API_KEY")

        if api_key:

            try:
                request.organization = Organization.objects.get(
                    api_key=api_key, is_active=True
                )
            except Organization.DoesNotExist:
                return JsonResponse({"error": "Invalid API key"}, status=401)
        else:
            request.organization = None

        return self.get_response(request)

    def _is_exempt(self, path):
        """Return True if *path* should skip API-key authentication."""
        return any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES)
