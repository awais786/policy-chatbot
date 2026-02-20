"""
LangChain-based chat history management for the chatbot.

Uses LangChain's BaseChatMessageHistory and RunnableWithMessageHistory
for proper conversation management. In-memory store with session eviction,
per-session message limits, TTL expiry, summarization and thread safety.

Older turns beyond `recent_window` are summarised into a compact SystemMessage
so long conversations stay context-rich without growing the prompt indefinitely.

NOTE: This in-memory implementation is suitable for development. For
production, replace with a Redis- or database-backed BaseChatMessageHistory.
"""

import logging
import re
import threading
import time
from typing import Callable, Dict, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# --- External required imports (LangChain must be present) ---------------------------------
try:
    from langchain_core.chat_history import BaseChatMessageHistory
    from langchain_core.messages import (
        AIMessage,
        BaseMessage,
        HumanMessage,
        SystemMessage,
    )
    LANGCHAIN_AVAILABLE = True
except Exception as exc:  # pragma: no cover - will be hit in environments without langchain
    raise ImportError(
        "langchain-core is required for chatbot history. Install it with: `pip install langchain-core` "
        "or add it to your environment requirements."
    ) from exc

# Provider clients (optional)
try:
    from langchain_ollama import ChatOllama  # type: ignore
except Exception:
    try:
        from langchain_community.chat_models.ollama import ChatOllama  # type: ignore
    except Exception:
        ChatOllama = None

try:
    from langchain_openai import ChatOpenAI  # type: ignore
except Exception:
    ChatOpenAI = None

# -----------------------------------------------------------------------------------------

DEFAULT_MAX_SESSIONS = 1000
DEFAULT_MAX_MESSAGES_PER_SESSION = 100
DEFAULT_SESSION_TTL_SECONDS = 3600  # 1 hour
DEFAULT_RECENT_WINDOW = 6  # messages kept verbatim; older ones get summarised

_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")

SummarizeFn = Callable[[str, str], str]


def _safe_session_id(session_id: str) -> str:
    """Return a log-safe representation of a session ID."""
    if _SESSION_ID_RE.match(session_id):
        return session_id
    return repr(session_id[:32])


def _format_messages_as_text(messages: List[BaseMessage]) -> str:
    """Convert a list of messages to a readable text block for summarisation."""
    lines: List[str] = []
    for msg in messages:
        role = getattr(msg, "type", "") or "user"
        content = getattr(msg, "content", "") or ""
        if not content:
            continue
        label = (
            "User" if role == "human"
            else "Assistant" if role == "ai"
            else role.capitalize()
        )
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


def _default_summarize(summary: str, new_messages_text: str) -> str:
    """Fallback summariser — just concatenates (no LLM call)."""
    if summary:
        return f"{summary}\n{new_messages_text}"
    return new_messages_text


class LangChainChatMessageHistory(BaseChatMessageHistory):
    """LangChain-compatible chat message history with rolling summarisation.

    Keeps the most recent `recent_window` messages verbatim.
    Older turns are summarised into a single SystemMessage so the LLM
    always has full conversational context without an ever-growing prompt.
    """

    def __init__(
        self,
        session_id: str,
        max_messages: int = DEFAULT_MAX_MESSAGES_PER_SESSION,
        recent_window: int = DEFAULT_RECENT_WINDOW,
        summarize_fn: Optional[SummarizeFn] = None,
    ):
        self.session_id = session_id
        self._messages: List[BaseMessage] = []
        self.max_messages = max_messages
        self._recent_window = max(int(recent_window), 2)
        self._summarize_fn: SummarizeFn = summarize_fn or _default_summarize
        self._summary: str = ""
        self._lock = threading.Lock()
        self.created_at: float = time.monotonic()
        self.last_activity: float = time.monotonic()

    @property
    def messages(self) -> List[BaseMessage]:  # type: ignore[override]
        """Return history: optional summary SystemMessage + recent verbatim messages."""
        with self._lock:
            items: List[BaseMessage] = []
            if self._summary and SystemMessage is not None:
                items.append(
                    SystemMessage(
                        content=f"Summary of earlier conversation:\n{self._summary}"
                    )
                )
            items.extend(self._messages)
            return list(items)

    def add_message(self, message: BaseMessage) -> None:
        """Append a message, summarising older turns when window is exceeded."""
        with self._lock:
            self._messages.append(message)
            self.last_activity = time.monotonic()

            # Summarise turns that fall outside the recent window
            if len(self._messages) > self._recent_window:
                older = self._messages[:-self._recent_window]
                older_text = _format_messages_as_text(older)
                if older_text:
                    try:
                        self._summary = self._summarize_fn(self._summary, older_text)
                    except Exception:
                        logger.warning(
                            "Summarisation failed for session %s; keeping existing summary",
                            _safe_session_id(self.session_id),
                        )
                self._messages = self._messages[-self._recent_window:]

    def clear(self) -> None:
        with self._lock:
            self._summary = ""
            self._messages.clear()


class LangChainSessionStore:
    """Thread-safe session store with LRU eviction, TTL expiry, and summarisation."""

    def __init__(
        self,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
        max_messages_per_session: int = DEFAULT_MAX_MESSAGES_PER_SESSION,
        session_ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
        recent_window: int = DEFAULT_RECENT_WINDOW,
        summarize_fn: Optional[SummarizeFn] = None,
    ):
        self._store: Dict[str, LangChainChatMessageHistory] = {}
        self._lock = threading.Lock()
        self.max_sessions = max_sessions
        self.max_messages_per_session = max_messages_per_session
        self.session_ttl_seconds = session_ttl_seconds
        self._recent_window = recent_window
        self._summarize_fn = summarize_fn

    def _evict_expired(self) -> None:
        """Remove sessions that have exceeded their TTL. Must be called under lock."""
        now = time.monotonic()
        expired = [
            sid for sid, hist in self._store.items()
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
                session_id,
                max_messages=self.max_messages_per_session,
                recent_window=self._recent_window,
                summarize_fn=self._summarize_fn,
            )
            self._store[session_id] = history
            logger.debug("Created new chat session: %s", _safe_session_id(session_id))
            return history

    def clear_session(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._store:
                del self._store[session_id]
                logger.debug("Cleared chat session: %s", _safe_session_id(session_id))
                return True
            return False

    def get_stats(self) -> Dict:
        with self._lock:
            total_messages = sum(len(h._messages) for h in self._store.values())
            summarised = sum(1 for h in self._store.values() if h._summary)
            return {
                "active_sessions": len(self._store),
                "total_messages": total_messages,
                "sessions_with_summary": summarised,
                "max_sessions": self.max_sessions,
                "max_messages_per_session": self.max_messages_per_session,
                "session_ttl_seconds": self.session_ttl_seconds,
                "recent_window": self._recent_window,
                "langchain_enabled": LANGCHAIN_AVAILABLE,
            }


# ---------------------------------------------------------------------------
# LLM summariser builder (uses top-level provider imports; no inline imports)
# ---------------------------------------------------------------------------

def _build_llm_summarize_fn() -> Optional[SummarizeFn]:
    """
    Return a summarise function backed by the configured LLM.
    Falls back to the simple concatenation summariser if LLM is unavailable.
    """
    try:
        provider = getattr(settings, "CHATBOT_LLM_PROVIDER", "ollama")
        model = getattr(settings, "CHATBOT_LLM_MODEL", "mistral")

        # Prefer ChatOllama when configured
        if provider == "ollama":
            if ChatOllama is None:
                raise RuntimeError("Ollama client not available")
            base_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
            llm = ChatOllama(model=model, base_url=base_url, temperature=0.1)
        elif provider == "openai":
            if ChatOpenAI is None:
                raise RuntimeError("OpenAI client not available")
            api_key = getattr(settings, "OPENAI_API_KEY", None)
            llm = ChatOpenAI(model=model, api_key=api_key, temperature=0.1)
        else:
            return None

        hm = HumanMessage if HumanMessage is not None else None

        def _summarize(existing_summary: str, new_messages_text: str) -> str:
            prompt = (
                "Summarise the following conversation turns into a concise paragraph "
                "that preserves key facts, decisions, and names.\n\n"
                f"Existing summary:\n{existing_summary}\n\n"
                f"New messages:\n{new_messages_text}\n\n"
                "Updated summary:"
            )
            # Prefer HumanMessage wrapper when available
            if hm is not None:
                result = llm.invoke([hm(content=prompt)])
            else:
                result = llm.invoke(prompt)
            return (getattr(result, "content", None) or str(result)).strip()

        return _summarize

    except Exception:
        logger.debug("LLM summariser unavailable, using fallback", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Public store factory used by LLM generation modules
# ---------------------------------------------------------------------------

_langchain_store: Optional[LangChainSessionStore] = None


def _get_singleton_store() -> Optional[LangChainSessionStore]:
    """Internal lazy singleton creator (keeps existing behaviour)."""
    global _langchain_store
    if _langchain_store is None and LANGCHAIN_AVAILABLE:
        _langchain_store = LangChainSessionStore(
            recent_window=int(getattr(settings, "CHAT_HISTORY_RECENT_WINDOW", DEFAULT_RECENT_WINDOW)),
            summarize_fn=_build_llm_summarize_fn(),
        )
    return _langchain_store


def get_history_store(summarize_fn: Optional[SummarizeFn] = None, recent_window: Optional[int] = None) -> Optional[LangChainSessionStore]:
    """Public factory that returns a session store compatible with LangChain runnable history.

    Args:
        summarize_fn: optional summariser function (if None the configured LLM summariser is used)
        recent_window: optional recent-window override

    Returns:
        LangChainSessionStore instance or None if LangChain components are unavailable.
    """
    if not LANGCHAIN_AVAILABLE:
        return None

    # If a global singleton already exists and no overrides requested, return it
    if summarize_fn is None and recent_window is None:
        return _get_singleton_store()

    # Otherwise create a new ephemeral store with provided options
    return LangChainSessionStore(
        recent_window=int(recent_window or getattr(settings, "CHAT_HISTORY_RECENT_WINDOW", DEFAULT_RECENT_WINDOW)),
        summarize_fn=summarize_fn or _build_llm_summarize_fn(),
    )


# Backwards-compatible public API names kept for existing callers
def get_session_history_for_langchain(
    session_id: Optional[str] = None,
    config: Optional[dict] = None,
    **kwargs: object,
) -> LangChainChatMessageHistory:
    store = _get_singleton_store()
    if store is None:
        raise RuntimeError("LangChain components not available")
    sid = session_id or (kwargs.get("session_id") if kwargs else None)
    if sid is None and config:
        sid = config.get("configurable", {}).get("session_id")
    if not sid:
        raise ValueError("session_id required in config['configurable']")
    return store.get_session_history(str(sid))


def add_user_message(session_id: str, message: str) -> None:
    store = _get_singleton_store()
    if store is None:
        return
    if HumanMessage is None:
        return
    store.get_session_history(session_id).add_message(HumanMessage(content=message))


def add_ai_message(session_id: str, message: str) -> None:
    store = _get_singleton_store()
    if store is None:
        return
    if AIMessage is None:
        return
    store.get_session_history(session_id).add_message(AIMessage(content=message))


def get_chat_store_stats() -> Dict:
    store = _get_singleton_store()
    if store is None:
        return {"active_sessions": 0, "total_messages": 0, "langchain_enabled": False}
    return store.get_stats()


def clear_chat_history(session_id: str) -> bool:
    store = _get_singleton_store()
    if store is None:
        return False
    return store.clear_session(session_id)


def get_recent_messages(session_id: str, count: int = 10) -> List[Dict]:
    """Return recent messages as simple dicts (used for query expansion)."""
    store = _get_singleton_store()
    if store is None:
        return []
    try:
        history = store.get_session_history(session_id)
        # Use raw _messages (not .messages) to skip the summary SystemMessage
        msgs = history._messages[-count:] if count > 0 else list(history._messages)
        result: List[Dict] = []
        for msg in msgs:
            if HumanMessage is not None and isinstance(msg, HumanMessage):
                msg_type = "user"
            elif AIMessage is not None and isinstance(msg, AIMessage):
                msg_type = "assistant"
            else:
                msg_type = "system"
            result.append({"content": msg.content, "type": msg_type})
        return result

    except Exception:
        logger.exception("Error retrieving recent messages")
        return []
