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
    by ID and attaches it as ``request.organization``.  Admin, docs, and health
    check paths are exempt so they work without a key.

    Currently using organization ID for simple testing - will be replaced with proper tokens later.
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
            org_identifier = api_key

            # Remove "org-" prefix if present
            if api_key.startswith('org-'):
                org_identifier = api_key[4:]

            request.organization = None

            # First, try UUID lookup (if it looks like a UUID)
            import uuid
            try:
                # This will raise ValueError if not a valid UUID
                uuid.UUID(org_identifier)
                # If we get here, it's a valid UUID format
                try:
                    request.organization = Organization.objects.get(
                        id=org_identifier, is_active=True
                    )
                except Organization.DoesNotExist:
                    pass  # Will try name lookup below
            except ValueError:
                # Not a valid UUID, skip UUID lookup
                pass

            # If UUID lookup didn't work, try name lookup
            if request.organization is None:
                try:
                    request.organization = Organization.objects.get(
                        name=org_identifier, is_active=True
                    )
                except Organization.DoesNotExist:
                    return JsonResponse({"error": "Organization not found"}, status=404)

            # If we still don't have an organization, return error
            if request.organization is None:
                return JsonResponse({"error": "Organization not found"}, status=404)
        else:
            request.organization = None

        return self.get_response(request)

    def _is_exempt(self, path):
        """Return True if *path* should skip API-key authentication."""
        return any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES)
