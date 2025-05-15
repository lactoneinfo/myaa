from __future__ import annotations
from typing import Optional
from myaa.data.cache import AgentStateCache
from myaa.logic.domain.message import Message
from myaa.logic.domain.state import AgentState, Status


class InputManager:
    def __init__(self, cache: AgentStateCache):
        self.cache = cache

    async def handle(self, session_key: str, message: Message) -> str:
        prev: Optional[AgentState] = await self.cache.get_by_session(session_key)
        if prev is None:
            state = AgentState.new(message)
        else:
            state = prev.copy()
            await self.cache.delete(prev.id)
            state.add_message(message)

        state.status = Status.running

        await self.cache.put(state)
        await self.cache.bind(session_key, state.id)
        return state.id
