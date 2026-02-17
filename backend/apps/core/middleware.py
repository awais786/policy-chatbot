"""
Custom middleware for the policy-chatbot project.

APIKeyAuthMiddleware — extracts organization from the X-API-Key header
and attaches it to the request. Will be implemented in a later todo.
"""


class APIKeyAuthMiddleware:
    """Authenticate requests via X-API-Key header."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # TODO: implement API key lookup and attach org to request
        return self.get_response(request)
