"""
Django management command to test search functionality from command line.
Usage: python manage.py test_search "your search query here"
"""

from django.core.management.base import BaseCommand, CommandError
import json

from apps.chatbot.services.search import VectorSearchService


class Command(BaseCommand):
    help = 'Test search functionality with a query string'

    def add_arguments(self, parser):
        parser.add_argument(
            'query',
            type=str,
            help='Search query string to test'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=5,
            help='Number of results to return (default: 5)'
        )
        parser.add_argument(
            '--min-similarity',
            type=float,
            default=0.3,
            help='Minimum similarity threshold (default: 0.3)'
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

    def handle(self, *args, **options):
        query = options['query']
        limit = options['limit']
        min_similarity = options['min_similarity']
        organization_id = options['organization_id']
        json_output = options['json']

        self.stdout.write(f"Testing search for: '{query}'")
        self.stdout.write(f"Parameters: limit={limit}, min_similarity={min_similarity}")
        self.stdout.write("-" * 60)

        try:
            # Create search service and perform search
            search_service = VectorSearchService(organization_id)
            results = search_service.search(
                query=query,
                limit=limit,
                min_similarity=min_similarity
            )

            if json_output:
                # Output in JSON format
                response = {
                    "query": query,
                    "results_count": len(results),
                    "results": results
                }
                self.stdout.write(json.dumps(response, indent=2, default=str))
            else:
                # Output in human-readable format
                self.stdout.write(f"\nFound {len(results)} results:")

                if not results:
                    self.stdout.write(self.style.WARNING("No results found. Try lowering --min-similarity threshold."))
                    return

                for i, result in enumerate(results, 1):
                    self.stdout.write(f"\n{i}. Document: {result.get('document_title', 'Unknown')}")
                    self.stdout.write(f"   Chunk Index: {result.get('chunk_index', 'N/A')}")
                    self.stdout.write(f"   Similarity: {result.get('similarity_score', 0):.4f}")
                    content = result.get('content', '')
                    preview = content[:200] + "..." if len(content) > 200 else content
                    self.stdout.write(f"   Content: {preview}")
                    self.stdout.write("-" * 40)

        except Exception as e:
            raise CommandError(f"Search failed: {e}")

        self.stdout.write(self.style.SUCCESS(f"\nSearch test completed for query: '{query}'"))
