from myaa.data.cache import AgentStateCache


class ChatAgent:
    def __init__(self, cache: AgentStateCache):
        self.cache = cache

    async def generate(self, as_id: str) -> str:
        state = await self.cache.get(as_id)
        if state is None:
            return "[ERROR] state not found"
        # dummy echo implementation
        reply = f"{state.context.message}"

        return reply
