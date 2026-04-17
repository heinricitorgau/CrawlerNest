from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ConversationTurn:
    """A single completed exchange in a conversation session."""

    role: str  # "user" | "assistant"
    content: str
    task_kind: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ConversationStore:
    """Thread-safe in-memory store for multi-turn conversation history.

    Keyed by ``session_id``.  Each session holds an ordered list of
    :class:`ConversationTurn` objects (user + assistant alternating).

    Args:
        max_turns_per_session: Hard cap on the number of turns kept per session.
            Oldest turns are evicted when the cap is exceeded.
        max_sessions: Maximum number of concurrent sessions to hold in memory.
            Oldest sessions are evicted LRU-style once the cap is hit.
    """

    def __init__(
        self,
        *,
        max_turns_per_session: int = 20,
        max_sessions: int = 500,
    ) -> None:
        self._max_turns = max_turns_per_session
        self._max_sessions = max_sessions
        # Ordered dict preserves insertion order for LRU eviction.
        self._sessions: dict[str, list[ConversationTurn]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_history(self, session_id: str) -> list[ConversationTurn]:
        """Return a snapshot of the turn list for *session_id* (never mutates it)."""
        with self._lock:
            return list(self._sessions.get(session_id, []))

    def append_user(
        self,
        session_id: str,
        *,
        content: str,
        task_kind: str = "",
    ) -> None:
        """Append a user turn to *session_id*, creating the session if needed."""
        turn = ConversationTurn(role="user", content=content, task_kind=task_kind)
        self._append(session_id, turn)

    def append_assistant(
        self,
        session_id: str,
        *,
        content: str,
        task_kind: str = "",
    ) -> None:
        """Append an assistant reply turn to *session_id*."""
        turn = ConversationTurn(role="assistant", content=content, task_kind=task_kind)
        self._append(session_id, turn)

    def clear_session(self, session_id: str) -> None:
        """Remove *session_id* entirely (no-op if not found)."""
        with self._lock:
            self._sessions.pop(session_id, None)

    def session_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _append(self, session_id: str, turn: ConversationTurn) -> None:
        with self._lock:
            if session_id not in self._sessions:
                if len(self._sessions) >= self._max_sessions:
                    # Evict the oldest session (first key in insertion order).
                    oldest = next(iter(self._sessions))
                    del self._sessions[oldest]
                self._sessions[session_id] = []
            else:
                # Move to end to mark as recently used (LRU bookkeeping).
                turns = self._sessions.pop(session_id)
                self._sessions[session_id] = turns

            self._sessions[session_id].append(turn)

            # Trim to max capacity — keep the most recent turns.
            if len(self._sessions[session_id]) > self._max_turns:
                self._sessions[session_id] = self._sessions[session_id][-self._max_turns :]
