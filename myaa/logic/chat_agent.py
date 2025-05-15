from myaa.data.cache import AgentStateCache
from myaa.logic.domain.message import Message


class ChatAgent:
    def __init__(self, cache: AgentStateCache):
        self.cache = cache

    async def generate(self, as_id: str) -> Message:
        state = await self.cache.get(as_id)
        if state is None:
            return Message(speaker="assistant", content="[ERROR] state not found")
        text = state.context.message.content
        return Message(speaker="assistant", content=text)
