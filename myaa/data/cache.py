from __future__ import annotations
import asyncio
import time
from typing import Dict, Optional, Iterable
from myaa.logic.domain.state import AgentState

_TTL = 60 * 30  # 30 min


class AgentStateCache:
    """In‑memory cache with TTL and session→AS mapping."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._store: Dict[str, AgentState] = {}
        self._session_map: Dict[str, str] = {}

    async def get(self, as_id: str) -> Optional[AgentState]:
        async with self._lock:
            state = self._store.get(as_id)
            if state and time.time() - state.updated_at < _TTL:
                return state
            return None

    async def get_by_session(self, session_key: str) -> Optional[AgentState]:
        as_id = self._session_map.get(session_key)
        return await self.get(as_id) if as_id else None

    async def put(self, state: AgentState, session_key: str) -> None:
        async with self._lock:
            self._store[state.id] = state
            self._session_map[session_key] = state.id

    async def list(self) -> Iterable[AgentState]:
        async with self._lock:
            return list(self._store.values())

    async def delete(self, as_id: str) -> None:
        async with self._lock:
            self._store.pop(as_id, None)
            for key, sid in list(self._session_map.items()):
                if sid == as_id:
                    self._session_map.pop(key)
