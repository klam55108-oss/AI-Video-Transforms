"""In-memory chat session management."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field


SESSION_TTL = 3600.0  # 1 hour
MAX_SESSIONS = 50


@dataclass
class ChatSession:
    """In-memory chat session."""

    session_id: str
    turns: list[tuple[str, str]] = field(default_factory=list)  # (role, content)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    def add_turn(self, role: str, content: str) -> None:
        """Add a conversation turn."""
        self.turns.append((role, content))
        self.last_activity = time.time()

    def build_prompt(self, message: str) -> str:
        """Build prompt with conversation history."""
        if not self.turns:
            return message
        # Include last 10 turns for context
        history = "\n".join(f"{r}: {c}" for r, c in self.turns[-10:])
        return f"Previous conversation:\n{history}\n\nUser: {message}"

    def is_expired(self) -> bool:
        """Check if session has expired."""
        return time.time() - self.last_activity > SESSION_TTL


class SessionManager:
    """Thread-safe session manager."""

    def __init__(self) -> None:
        self._sessions: dict[str, ChatSession] = {}
        self._lock = threading.Lock()

    def get_or_create(self, session_id: str | None) -> ChatSession:
        """Get existing session or create a new one."""
        with self._lock:
            self._cleanup()
            if session_id and session_id in self._sessions:
                return self._sessions[session_id]
            new_id = session_id or str(uuid.uuid4())[:8]
            session = ChatSession(session_id=new_id)
            self._sessions[new_id] = session
            return session

    def clear(self, session_id: str) -> bool:
        """Clear a session by ID. Returns True if session existed."""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def list_all(self) -> list[dict[str, str | int]]:
        """List all active sessions."""
        with self._lock:
            self._cleanup()
            return [
                {"id": s.session_id, "turns": len(s.turns)}
                for s in self._sessions.values()
            ]

    def _cleanup(self) -> None:
        """Remove expired sessions."""
        expired = [k for k, v in self._sessions.items() if v.is_expired()]
        for k in expired:
            del self._sessions[k]


# Singleton
_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    """Get or create the session manager singleton."""
    global _manager
    if _manager is None:
        _manager = SessionManager()
    return _manager
