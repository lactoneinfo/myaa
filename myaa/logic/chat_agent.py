from myaa.data.cache import AgentStateCache
from myaa.logic.domain.message import Message


class ChatAgent:
    def __init__(self, cache: AgentStateCache):
        self.cache = cache

    async def generate(self, as_id: str) -> Message:
        state = await self.cache.get(as_id)
        assert state is not None, f"AgentState not found for {as_id}"
        assert state.context.message is not None, "Current message must not be None"

        text = state.context.message.content
        return Message(speaker="assistant", content=text)
