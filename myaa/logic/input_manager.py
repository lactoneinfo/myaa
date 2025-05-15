from __future__ import annotations
from typing import Optional
from myaa.data.cache import AgentStateCache
from myaa.domain.state import AgentState, Status
from myaa.domain.command import ChatCommand


class InputManager:
    def __init__(self, cache: AgentStateCache):
        self.cache = cache

    async def handle(self, session_key: str, command: ChatCommand) -> str:
        prev: Optional[AgentState] = await self.cache.get_by_session(session_key)
        if prev is None:
            state = AgentState.new(command.message, responder_id=command.responder_id)
        else:
            state = prev.copy()
            await self.cache.delete(prev.id)
            state.responder_id = command.responder_id
            state.add_message(command.message)

        state.status = Status.running

        await self.cache.put(state)
        await self.cache.bind(session_key, state.id)
        return state.id
