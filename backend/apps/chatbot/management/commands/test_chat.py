"""
Django management command to test chat functionality from command line.
Usage: python manage.py test_chat "your chat message here"
"""

from django.core.management.base import BaseCommand, CommandError
import json
import uuid

from apps.chatbot.services.search import VectorSearchService
from apps.chatbot.services.providers import create_rag_chatbot


class Command(BaseCommand):
    help = 'Test chat functionality with a message string'

    def add_arguments(self, parser):
        parser.add_argument(
            'message',
            type=str,
            help='Chat message to send'
        )
        parser.add_argument(
            '--session-id',
            type=str,
            help='Session ID for conversation continuity (auto-generated if not provided)'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=5,
            help='Number of search results to use for context (default: 5)'
        )
        parser.add_argument(
            '--min-similarity',
            type=float,
            default=0.3,
            help='Minimum similarity threshold for search (default: 0.3)'
        )
        parser.add_argument(
            '--organization-id',
            type=str,
            default="dcbd2e32-923b-420d-a58a-c6523da4af6d",
            help='Organization ID to search within'
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output results in JSON format'
        )
        parser.add_argument(
            '--show-sources',
            action='store_true',
            help='Show source documents used for the response'
        )

    def handle(self, *args, **options):
        message = options['message']
        session_id = options['session_id'] or str(uuid.uuid4())
        limit = options['limit']
        min_similarity = options['min_similarity']
        organization_id = options['organization_id']
        json_output = options['json']
        show_sources = options['show_sources']

        self.stdout.write(f"Testing chat with message: '{message}'")
        self.stdout.write(f"Session ID: {session_id}")
        self.stdout.write(f"Parameters: limit={limit}, min_similarity={min_similarity}")
        self.stdout.write("-" * 60)

        try:
            # Step 1: Search for relevant documents
            search_service = VectorSearchService(organization_id)
            search_results = search_service.search(
                query=message,
                limit=limit,
                min_similarity=min_similarity
            )

            self.stdout.write(f"Found {len(search_results)} relevant documents")

            # Step 2: Generate chat response using RAG
            chatbot = create_rag_chatbot(organization_id)
            result = chatbot.generate_answer(message, search_results, session_id)

            if json_output:
                # Output in JSON format
                response = {
                    "session_id": session_id,
                    "message": result["answer"],
                    "sources": search_results if show_sources else [],
                    "metadata": {
                        "sources_used": result["sources_used"],
                        "provider": result["provider"],
                        "model": result["model"],
                        "history_enabled": result["history_enabled"],
                        "query": message
                    }
                }
                self.stdout.write(json.dumps(response, indent=2, default=str))
            else:
                # Output in human-readable format
                self.stdout.write(f"\n🤖 AI Response:")
                self.stdout.write(f"{result['answer']}")

                self.stdout.write(f"\n📊 Metadata:")
                self.stdout.write(f"   Provider: {result['provider']}")
                self.stdout.write(f"   Model: {result['model']}")
                self.stdout.write(f"   Sources used: {result['sources_used']}")
                self.stdout.write(f"   History enabled: {result['history_enabled']}")

                if show_sources and search_results:
                    self.stdout.write(f"\n📚 Source Documents:")
                    for i, source in enumerate(search_results, 1):
                        self.stdout.write(f"\n{i}. Document: {source.get('document_title', 'Unknown')}")
                        self.stdout.write(f"   Similarity: {source.get('similarity_score', 0):.4f}")
                        content = source.get('content', '')
                        preview = content[:150] + "..." if len(content) > 150 else content
                        self.stdout.write(f"   Content: {preview}")
                        self.stdout.write("-" * 30)

        except Exception as e:
            raise CommandError(f"Chat failed: {e}")

        self.stdout.write(self.style.SUCCESS(f"\nChat test completed!"))
        self.stdout.write(f"Use the same --session-id '{session_id}' for conversation continuity.")
