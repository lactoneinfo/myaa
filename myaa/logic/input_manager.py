from __future__ import annotations
from typing import Optional
from myaa.data.cache import AgentStateCache
from myaa.logic.agent_state import AgentState, Status


class InputManager:
    def __init__(self, cache: AgentStateCache):
        self.cache = cache

    async def handle(self, session_key: str, text: str) -> str:
        prev: Optional[AgentState] = await self.cache.get_by_session(session_key)
        if prev is None:
            state = AgentState.new()
        else:
            state = prev.copy()
            await self.cache.delete(prev.id)

        state.status = Status.running
        state.add_message(text)

        await self.cache.put(state, session_key)
        return state.id
