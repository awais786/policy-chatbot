"""
LangChain-based chat history management for the chatbot.

Uses LangChain's BaseChatMessageHistory and RunnableWithMessageHistory
for proper conversation management. In-memory store with session eviction,
per-session message limits, TTL expiry, and thread safety.

NOTE: This in-memory implementation is suitable for development. For
production, replace with a Redis- or database-backed BaseChatMessageHistory.
"""

import logging
import re
import threading
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from langchain_core.chat_history import BaseChatMessageHistory
    from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

    LANGCHAIN_AVAILABLE = True
except ImportError:
    BaseChatMessageHistory = object  # type: ignore[assignment,misc]
    BaseMessage = None
    HumanMessage = None
    AIMessage = None
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain components not available, falling back to simple storage")

DEFAULT_MAX_SESSIONS = 1000
DEFAULT_MAX_MESSAGES_PER_SESSION = 100
DEFAULT_SESSION_TTL_SECONDS = 3600  # 1 hour

_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")


def _safe_session_id(session_id: str) -> str:
    """Return a log-safe representation of a session ID."""
    if _SESSION_ID_RE.match(session_id):
        return session_id
    return repr(session_id[:32])


class LangChainChatMessageHistory(BaseChatMessageHistory):
    """LangChain-compatible chat message history stored in memory.

    Enforces a maximum number of messages per session. Oldest messages
    are discarded when the limit is reached.
    """

    def __init__(
        self,
        session_id: str,
        max_messages: int = DEFAULT_MAX_MESSAGES_PER_SESSION,
    ):
        self.session_id = session_id
        self._messages: List[BaseMessage] = []
        self.max_messages = max_messages
        self.created_at: float = time.monotonic()
        self.last_activity: float = time.monotonic()

    @property
    def messages(self) -> List[BaseMessage]:  # type: ignore[override]
        return list(self._messages)

    def add_message(self, message: BaseMessage) -> None:
        """Add a message, evicting the oldest if the limit is reached."""
        if len(self._messages) >= self.max_messages:
            self._messages = self._messages[-(self.max_messages - 1):]
        self._messages.append(message)
        self.last_activity = time.monotonic()

    def clear(self) -> None:
        self._messages.clear()


class LangChainSessionStore:
    """Thread-safe session store with LRU eviction and TTL expiry."""

    def __init__(
        self,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
        max_messages_per_session: int = DEFAULT_MAX_MESSAGES_PER_SESSION,
        session_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
    ):
        self._store: Dict[str, LangChainChatMessageHistory] = {}
        self._lock = threading.Lock()
        self.max_sessions = max_sessions
        self.max_messages_per_session = max_messages_per_session
        self.session_ttl_seconds = session_ttl_seconds

    def _evict_expired(self) -> None:
        """Remove sessions that have exceeded their TTL. Must be called under lock."""
        now = time.monotonic()
        expired = [
            sid
            for sid, hist in self._store.items()
            if (now - hist.last_activity) > self.session_ttl_seconds
        ]
        for sid in expired:
            del self._store[sid]
        if expired:
            logger.info("Evicted %d expired sessions", len(expired))

    def get_session_history(self, session_id: str) -> LangChainChatMessageHistory:
        """Get or create a chat message history for a session (thread-safe)."""
        with self._lock:
            existing = self._store.get(session_id)
            if existing is not None:
                existing.last_activity = time.monotonic()
                return existing

            self._evict_expired()

            if len(self._store) >= self.max_sessions:
                oldest_id = min(
                    self._store, key=lambda k: self._store[k].last_activity,
                )
                del self._store[oldest_id]
                logger.info("Evicted oldest session to stay within limit")

            history = LangChainChatMessageHistory(
                session_id, max_messages=self.max_messages_per_session,
            )
            self._store[session_id] = history
            logger.debug(
                "Created new chat session: %s", _safe_session_id(session_id),
            )
            return history

    def clear_session(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._store:
                del self._store[session_id]
                logger.debug(
                    "Cleared chat session: %s", _safe_session_id(session_id),
                )
                return True
            return False

    def get_stats(self) -> Dict:
        with self._lock:
            total_messages = sum(
                len(hist._messages) for hist in self._store.values()
            )
            return {
                "active_sessions": len(self._store),
                "total_messages": total_messages,
                "max_sessions": self.max_sessions,
                "max_messages_per_session": self.max_messages_per_session,
                "session_ttl_seconds": self.session_ttl_seconds,
                "langchain_enabled": LANGCHAIN_AVAILABLE,
            }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_langchain_store: Optional[LangChainSessionStore] = (
    LangChainSessionStore() if LANGCHAIN_AVAILABLE else None
)


def get_session_history_for_langchain(
    session_id: Optional[str] = None,
    config: Optional[dict] = None,
    **kwargs: object,
) -> LangChainChatMessageHistory:
    """Return a LangChain-compatible history for ``RunnableWithMessageHistory``.

    Accepts session_id directly or via config["configurable"]["session_id"]
    to support different LangChain versions.
    """
    if not LANGCHAIN_AVAILABLE or _langchain_store is None:
        raise RuntimeError("LangChain components not available")
    sid = session_id or (kwargs.get("session_id") if kwargs else None)
    if sid is None and config:
        sid = config.get("configurable", {}).get("session_id")
    if not sid:
        raise ValueError("session_id required in config['configurable']")
    return _langchain_store.get_session_history(str(sid))


def add_user_message(session_id: str, message: str) -> None:
    if not LANGCHAIN_AVAILABLE or _langchain_store is None:
        return
    history = _langchain_store.get_session_history(session_id)
    history.add_message(HumanMessage(content=message))


def add_ai_message(session_id: str, message: str) -> None:
    if not LANGCHAIN_AVAILABLE or _langchain_store is None:
        return
    history = _langchain_store.get_session_history(session_id)
    history.add_message(AIMessage(content=message))


def get_chat_store_stats() -> Dict:
    if not LANGCHAIN_AVAILABLE or _langchain_store is None:
        return {
            "active_sessions": 0,
            "total_messages": 0,
            "max_sessions": 0,
            "langchain_enabled": False,
        }
    return _langchain_store.get_stats()


def clear_chat_history(session_id: str) -> bool:
    if not LANGCHAIN_AVAILABLE or _langchain_store is None:
        return False
    return _langchain_store.clear_session(session_id)


def get_recent_messages(session_id: str, count: int = 10) -> List[Dict]:
    """Return recent messages in a simple dict format for display / fallback prompts."""
    if not LANGCHAIN_AVAILABLE or _langchain_store is None:
        return []

    try:
        history = _langchain_store.get_session_history(session_id)
        msgs = history.messages[-count:] if count > 0 else history.messages

        result: List[Dict] = []
        for msg in msgs:
            if isinstance(msg, HumanMessage):
                msg_type = "user"
            elif isinstance(msg, AIMessage):
                msg_type = "assistant"
            else:
                msg_type = "system"
            result.append({"content": msg.content, "type": msg_type})
        return result

    except Exception:
        logger.exception("Error retrieving recent messages")
        return []
