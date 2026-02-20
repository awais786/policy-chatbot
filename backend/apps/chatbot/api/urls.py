"""
URL patterns for the chatbot API (mounted at api/v1/chat/).
"""

from django.urls import path

from .views import search_documents, chat_with_documents, chat_stats, health_check, list_documents

app_name = "chatbot"

urlpatterns = [
    path("search/", search_documents, name="search"),
    path("documents/", list_documents, name="list_documents"),
    path("", chat_with_documents, name="chat"),
    path("stats/", chat_stats, name="stats"),
    path("health/", health_check, name="health"),
]
