"""Expiring in-memory storage for active validation sessions."""

from threading import RLock
from time import monotonic
from uuid import uuid4

from app.validation.dataset_service import ValidationService

SESSION_TTL_SECONDS = 60 * 60


class ValidationSessionStore:
    """Thread-safe, expiring validation session storage."""

    def __init__(self, ttl_seconds: int = SESSION_TTL_SECONDS) -> None:
        self._sessions: dict[str, tuple[float, ValidationService]] = {}
        self._ttl_seconds = ttl_seconds
        self._lock = RLock()

    def put(self, service: ValidationService) -> str:
        session_id = uuid4().hex
        with self._lock:
            self._remove_expired()
            self._sessions[session_id] = (monotonic(), service)
        return session_id

    def get(self, session_id: str | None) -> ValidationService | None:
        if not session_id:
            return None
        with self._lock:
            self._remove_expired()
            stored = self._sessions.get(session_id)
            if not stored:
                return None
            self._sessions[session_id] = (monotonic(), stored[1])
            return stored[1]

    def _remove_expired(self) -> None:
        cutoff = monotonic() - self._ttl_seconds
        expired = [
            session_id
            for session_id, (last_accessed, _) in self._sessions.items()
            if last_accessed < cutoff
        ]
        for session_id in expired:
            del self._sessions[session_id]
