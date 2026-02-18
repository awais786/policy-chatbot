"""
In-memory chat history management for the chatbot.

Provides simple in-memory chat history storage without database persistence.
Chat sessions are maintained in memory only and are lost when the server restarts.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class InMemoryChatHistory:
    """Simple in-memory chat history storage."""

    def __init__(self, session_id: str, max_messages: int = 20):
        self.session_id = session_id
        self.messages: List[Dict] = []
        self.max_messages = max_messages
        self.created_at = datetime.now()
        self.last_activity = datetime.now()

    def add_message(self, message: str, message_type: str = "user") -> None:
        """Add a message to the history."""
        self.messages.append({
            "content": message,
            "type": message_type,
            "timestamp": datetime.now()
        })
        self.last_activity = datetime.now()

        # Keep only the most recent messages to prevent memory bloat
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]

    def get_recent_messages(self, count: int = 10) -> List[Dict]:
        """Get the most recent messages."""
        return self.messages[-count:] if count > 0 else self.messages

    def clear(self) -> None:
        """Clear the chat history."""
        self.messages.clear()

    def is_expired(self, max_age_hours: int = 24) -> bool:
        """Check if the session has expired."""
        return datetime.now() - self.last_activity > timedelta(hours=max_age_hours)


class InMemoryChatStore:
    """Manages in-memory chat histories for different sessions."""

    def __init__(self, max_sessions: int = 1000, cleanup_interval_minutes: int = 60):
        self.sessions: Dict[str, InMemoryChatHistory] = {}
        self.max_sessions = max_sessions
        self.cleanup_interval_minutes = cleanup_interval_minutes
        self.last_cleanup = datetime.now()

    def get_session_history(self, session_id: str) -> InMemoryChatHistory:
        """Get or create chat history for a session."""
        # Perform periodic cleanup
        self._cleanup_expired_sessions()

        if session_id not in self.sessions:
            # Create new session if we haven't hit the limit
            if len(self.sessions) >= self.max_sessions:
                # Remove oldest session to make room
                oldest_session_id = min(
                    self.sessions.keys(),
                    key=lambda k: self.sessions[k].last_activity
                )
                del self.sessions[oldest_session_id]
                logger.info(f"Removed oldest session {oldest_session_id} to make room")

            self.sessions[session_id] = InMemoryChatHistory(session_id)
            logger.info(f"Created new chat session: {session_id}")

        return self.sessions[session_id]

    def clear_session(self, session_id: str) -> bool:
        """Clear history for a specific session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Cleared chat session: {session_id}")
            return True
        return False

    def _cleanup_expired_sessions(self, max_age_hours: int = 24) -> None:
        """Remove expired sessions to prevent memory bloat."""
        now = datetime.now()

        # Only run cleanup if enough time has passed
        if now - self.last_cleanup < timedelta(minutes=self.cleanup_interval_minutes):
            return

        expired_sessions = [
            session_id for session_id, history in self.sessions.items()
            if history.is_expired(max_age_hours)
        ]

        for session_id in expired_sessions:
            del self.sessions[session_id]

        if expired_sessions:
            logger.info(f"Cleaned up {len(expired_sessions)} expired chat sessions")

        self.last_cleanup = now

    def get_session_count(self) -> int:
        """Get the current number of active sessions."""
        return len(self.sessions)

    def get_stats(self) -> Dict:
        """Get statistics about the chat store."""
        total_messages = sum(len(hist.messages) for hist in self.sessions.values())
        return {
            "active_sessions": len(self.sessions),
            "total_messages": total_messages,
            "max_sessions": self.max_sessions,
            "last_cleanup": self.last_cleanup
        }


# Global in-memory chat store instance
_chat_store = InMemoryChatStore()


def get_chat_history(session_id: str) -> InMemoryChatHistory:
    """
    Get chat history for a session.

    Args:
        session_id: Unique identifier for the chat session

    Returns:
        InMemoryChatHistory instance for the session
    """
    return _chat_store.get_session_history(session_id)


def clear_chat_history(session_id: str) -> bool:
    """
    Clear chat history for a session.

    Args:
        session_id: Unique identifier for the chat session

    Returns:
        True if session was found and cleared, False otherwise
    """
    return _chat_store.clear_session(session_id)


def get_chat_store_stats() -> Dict:
    """Get statistics about the in-memory chat store."""
    return _chat_store.get_stats()
