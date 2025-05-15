from myaa.data.cache import AgentStateCache
from myaa.logic.domain.state import Status
from myaa.logic.domain.message import Message


class OutputManager:
    def __init__(self, cache: AgentStateCache):
        self.cache = cache

    async def finalize(self, as_id: str, reply: Message) -> None:
        state = await self.cache.get(as_id)
        if state is None:
            return
        state.add_message(reply)
        state.status = Status.ready
        await self.cache.put(state, session_key="_dummy")
