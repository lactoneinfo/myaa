"""Resolve <session_key> → <thread_id> and keep mapping in‑memory."""

from typing import Dict


class SessionManager:
    """Simple in‑memory resolver (swap with Redis if needed)."""

    def __init__(self):
        self._map: Dict[str, str] = {}
        self._counter = 0

    def resolve(self, session_key: str) -> str:
        """Return existing thread_id or allocate a new one."""
        if session_key not in self._map:
            self._counter += 1
            self._map[session_key] = str(self._counter)
        return self._map[session_key]


    def list_thread_ids(self) -> list[str]:
        return list(self._map.values())