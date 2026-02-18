"""
LLM Generation Module for RAG Chatbot - OpenAI and Ollama Only.

This module handles LLM generation using only OpenAI and Ollama providers
with a simplified, clean implementation.
"""

import logging
from typing import Any, List, Optional, Dict

from django.conf import settings

logger = logging.getLogger(__name__)

# Import only what we need for OpenAI and Ollama
try:
    from langchain_openai import ChatOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    ChatOpenAI = None
    OPENAI_AVAILABLE = False

try:
    from langchain_community.llms import Ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    try:
        from langchain.llms import Ollama
        OLLAMA_AVAILABLE = True
    except ImportError:
        Ollama = None
        OLLAMA_AVAILABLE = False


class LLMProvider:
    """Simple LLM provider that supports only OpenAI and Ollama."""

    def __init__(self, provider_type: str = None, model: str = None):
        """Initialize LLM provider.

        Args:
            provider_type: 'openai' or 'ollama'
            model: Model name to use
        """
        self.provider_type = provider_type or getattr(settings, 'CHATBOT_LLM_PROVIDER', 'ollama')
        self.model = model or getattr(settings, 'CHATBOT_LLM_MODEL', 'mistral')
        self.llm = self._create_llm()

    def _create_llm(self):
        """Create the appropriate LLM instance."""
        if self.provider_type == 'openai':
            return self._create_openai_llm()
        elif self.provider_type == 'ollama':
            return self._create_ollama_llm()
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider_type}")

    def _create_openai_llm(self):
        """Create OpenAI ChatGPT instance."""
        if not OPENAI_AVAILABLE:
            raise ImportError("langchain-openai is required for OpenAI support")

        api_key = getattr(settings, 'OPENAI_API_KEY', None)
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")

        return ChatOpenAI(
            model=self.model,
            api_key=api_key,
            temperature=0.1,  # Low temperature for more consistent responses
        )

    def _create_ollama_llm(self):
        """Create Ollama LLM instance."""
        if not OLLAMA_AVAILABLE:
            raise ImportError("langchain-community is required for Ollama support")

        base_url = getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434')

        return Ollama(
            model=self.model,
            base_url=base_url,
            temperature=0.1,
        )

    def generate_response(self, prompt: str) -> str:
        """Generate response using the configured LLM."""
        try:
            result = self.llm.invoke(prompt)

            # Handle different response formats
            if hasattr(result, 'content'):
                return str(result.content)
            elif isinstance(result, str):
                return result
            else:
                return str(result)

        except Exception as e:
            logger.error(f"LLM generation failed with {self.provider_type}: {e}")
            raise


class RAGChatbot:
    """Simple RAG chatbot using document search and LLM generation."""

    def __init__(self, organization_id: str):
        """Initialize RAG chatbot for a specific organization."""
        self.organization_id = organization_id
        self.llm_provider = LLMProvider()
        self.prompt_template = self._get_prompt_template()
        self.history_enabled = getattr(settings, 'CHATBOT_ENABLE_CHAT_HISTORY', True)

    def _get_prompt_template(self) -> str:
        """Get prompt template from settings."""
        return getattr(
            settings,
            "CHATBOT_PROMPT_TEMPLATE",
            """You are a knowledgeable assistant helping users find information from documents.

**Instructions:**
1. Answer ONLY using information from the context below
2. If the context contains the answer, provide a clear response
3. Cite the source document when possible
4. If the context doesn't contain enough information, say "I don't have enough information to answer that question."
5. Be concise but complete

**Context:**
{context}

**Question:**
{question}

**Answer:**"""
        )

    def _format_context_from_search_results(self, search_results: List[Dict]) -> str:
        """Format search results into context string."""
        if not search_results:
            return "No relevant documents found."

        context_parts = []
        for i, result in enumerate(search_results, 1):
            document_title = result.get('document_title', 'Unknown Document')
            content = result.get('content', '')
            similarity_score = result.get('similarity_score', 0)

            context_parts.append(
                f"[Source {i} - {document_title} (relevance: {similarity_score:.2f})]:\n{content}"
            )

        return "\n\n".join(context_parts)

    def _truncate_context(self, context: str, max_chars: int = None) -> str:
        """Truncate context if it's too long."""
        max_chars = max_chars or getattr(settings, 'CHATBOT_MAX_CONTEXT_CHARS', 8000)

        if not max_chars or len(context) <= max_chars:
            return context

        # Try to truncate at sentence boundaries
        truncated = context[:max_chars - 3]

        # Find the last sentence ending
        for punct in ['.', '!', '?']:
            last_punct = truncated.rfind(punct)
            if last_punct > max_chars * 0.7:  # Keep at least 70% of content
                return truncated[:last_punct + 1]

        return truncated + "..."

    def _build_prompt_with_history(self, question: str, context: str, session_id: str = None) -> str:
        """Build prompt including chat history if enabled and session_id provided."""
        if not self.history_enabled or not session_id:
            # No history - use simple prompt
            return self.prompt_template.format(context=context, question=question)

        # Get chat history for this session
        from apps.chatbot.services.chat_history import get_chat_history
        chat_history = get_chat_history(session_id)
        recent_messages = chat_history.get_recent_messages(count=6)  # Get last 6 messages

        # Build conversation context
        if recent_messages:
            conversation_context = "\n**Previous conversation:**\n"
            for msg in recent_messages:
                role = "User" if msg["type"] == "user" else "Assistant"
                conversation_context += f"{role}: {msg['content']}\n"
            conversation_context += "\n"
        else:
            conversation_context = ""

        # Enhanced prompt template with history
        history_prompt = f"""You are a knowledgeable assistant helping users find information from documents.

{conversation_context}**Instructions:**
1. Answer ONLY using information from the context below
2. Consider the conversation history for context, but base your answer on the provided documents
3. If the context contains the answer, provide a clear response
4. Cite the source document when possible
5. If the context doesn't contain enough information, say "I don't have enough information to answer that question."
6. Be concise but complete

**Context:**
{context}

**Current Question:**
{question}

**Answer:**"""

        return history_prompt

    def generate_answer(self, question: str, search_results: List[Dict], session_id: str = None) -> Dict[str, Any]:
        """Generate answer using search results and LLM, optionally maintaining chat history."""
        try:
            # Format context from search results
            context = self._format_context_from_search_results(search_results)
            context = self._truncate_context(context)

            # Create prompt (with or without history)
            prompt = self._build_prompt_with_history(question, context, session_id)

            # Generate response
            answer = self.llm_provider.generate_response(prompt)

            # Store in chat history if enabled
            if self.history_enabled and session_id:
                from apps.chatbot.services.chat_history import get_chat_history
                chat_history = get_chat_history(session_id)
                chat_history.add_message(question, "user")
                chat_history.add_message(answer, "assistant")

            return {
                "answer": answer,
                "sources_used": len(search_results),
                "context_length": len(context),
                "provider": self.llm_provider.provider_type,
                "model": self.llm_provider.model,
                "history_enabled": self.history_enabled and bool(session_id)
            }

        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return {
                "answer": "I'm sorry, I encountered an error while generating the response. Please try again.",
                "error": str(e),
                "sources_used": 0,
                "context_length": 0,
                "history_enabled": False
            }


def get_llm_provider(provider_type: str = None, model: str = None) -> LLMProvider:
    """Factory function to get LLM provider."""
    return LLMProvider(provider_type, model)


def create_rag_chatbot(organization_id: str) -> RAGChatbot:
    """Factory function to create RAG chatbot."""
    return RAGChatbot(organization_id)


__all__ = ["LLMProvider", "RAGChatbot", "get_llm_provider", "create_rag_chatbot"]
