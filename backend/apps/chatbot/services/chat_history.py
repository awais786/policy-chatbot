"""
LangChain-based chat history management for the chatbot.

Uses LangChain's ChatMessageHistory and RunnableWithMessageHistory
for proper conversation management.
"""

import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from langchain_core.chat_history import BaseChatMessageHistory
    from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
    from langchain_core.runnables.history import RunnableWithMessageHistory
    LANGCHAIN_AVAILABLE = True
except ImportError:
    BaseChatMessageHistory = None
    BaseMessage = None
    HumanMessage = None
    AIMessage = None
    RunnableWithMessageHistory = None
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain components not available, falling back to simple storage")


class LangChainChatMessageHistory(BaseChatMessageHistory):
    """LangChain-compatible chat message history that stores messages in memory."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages: list[BaseMessage] = []
        self.created_at = datetime.now()
        self.last_activity = datetime.now()

    def add_message(self, message: BaseMessage) -> None:
        """Add a message to the store"""
        self.messages.append(message)
        self.last_activity = datetime.now()

    def clear(self) -> None:
        """Clear all messages from the store"""
        self.messages.clear()


class LangChainSessionStore:
    """Manages LangChain chat message histories for different sessions."""

    def __init__(self, max_sessions: int = 1000):
        self.store: Dict[str, LangChainChatMessageHistory] = {}
        self.max_sessions = max_sessions

    def get_session_history(self, session_id: str) -> LangChainChatMessageHistory:
        """Get or create a chat message history for a session."""
        if session_id not in self.store:
            if len(self.store) >= self.max_sessions:
                # Remove oldest session to make room
                oldest_session_id = min(
                    self.store.keys(),
                    key=lambda k: self.store[k].last_activity
                )
                del self.store[oldest_session_id]
                logger.info(f"Removed oldest session {oldest_session_id} to make room")

            self.store[session_id] = LangChainChatMessageHistory(session_id)
            logger.info(f"Created new LangChain chat session: {session_id}")

        return self.store[session_id]

    def clear_session(self, session_id: str) -> bool:
        """Clear history for a specific session."""
        if session_id in self.store:
            del self.store[session_id]
            logger.info(f"Cleared LangChain chat session: {session_id}")
            return True
        return False

    def get_stats(self) -> Dict:
        """Get statistics about the session store."""
        total_messages = sum(len(hist.messages) for hist in self.store.values())
        return {
            "active_sessions": len(self.store),
            "total_messages": total_messages,
            "max_sessions": self.max_sessions,
            "langchain_enabled": LANGCHAIN_AVAILABLE,
            "last_updated": datetime.now()
        }


# Global LangChain session store instance
_langchain_store = LangChainSessionStore() if LANGCHAIN_AVAILABLE else None


def get_session_history_for_langchain(session_id: str) -> LangChainChatMessageHistory:
    """
    Get LangChain-compatible chat history for a session.
    This function signature is required by RunnableWithMessageHistory.

    Args:
        session_id: Unique identifier for the chat session

    Returns:
        LangChainChatMessageHistory instance for the session
    """
    if not LANGCHAIN_AVAILABLE or not _langchain_store:
        raise RuntimeError("LangChain components not available")

    return _langchain_store.get_session_history(session_id)


def add_user_message(session_id: str, message: str) -> None:
    """Add a user message to the chat history."""
    if not LANGCHAIN_AVAILABLE or not _langchain_store:
        logger.warning("LangChain not available, message not stored")
        return

    history = _langchain_store.get_session_history(session_id)
    history.add_message(HumanMessage(content=message))


def add_ai_message(session_id: str, message: str) -> None:
    """Add an AI message to the chat history."""
    if not LANGCHAIN_AVAILABLE or not _langchain_store:
        logger.warning("LangChain not available, message not stored")
        return

    history = _langchain_store.get_session_history(session_id)
    history.add_message(AIMessage(content=message))


def get_chat_store_stats() -> Dict:
    """Get statistics about the LangChain chat store."""
    if not LANGCHAIN_AVAILABLE or not _langchain_store:
        return {
            "active_sessions": 0,
            "total_messages": 0,
            "max_sessions": 0,
            "langchain_enabled": False,
            "error": "LangChain components not available"
        }

    return _langchain_store.get_stats()


def clear_chat_history(session_id: str) -> bool:
    """
    Clear chat history for a session.

    Args:
        session_id: Unique identifier for the chat session

    Returns:
        True if session was found and cleared, False otherwise
    """
    if not LANGCHAIN_AVAILABLE or not _langchain_store:
        return False

    return _langchain_store.clear_session(session_id)


def get_recent_messages(session_id: str, count: int = 10) -> list:
    """
    Get recent messages from a session for display purposes.

    Returns messages in a simple format for inspection.
    """
    if not LANGCHAIN_AVAILABLE or not _langchain_store:
        return []

    try:
        history = _langchain_store.get_session_history(session_id)
        messages = history.messages[-count:] if count > 0 else history.messages

        # Convert LangChain messages to simple dict format for display
        result = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                msg_type = "user"
            elif isinstance(msg, AIMessage):
                msg_type = "assistant"
            else:
                msg_type = "system"

            result.append({
                "content": msg.content,
                "type": msg_type,
                "timestamp": datetime.now()  # LangChain messages don't have timestamps by default
            })

        return result
    except Exception as e:
        logger.error(f"Error getting recent messages for session {session_id}: {e}")
        return []
