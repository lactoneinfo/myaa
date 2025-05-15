from myaa.logic.domain.message import Message
from myaa.logic.formatter.prompt_formatter import PromptFormatter
from myaa.logic.provider.base import get_provider


class ChatAgent:
    def __init__(self, cache):
        self.cache = cache
        self.provider = get_provider()

    async def generate(self, as_id: str) -> Message:
        state = await self.cache.get(as_id)
        assert state is not None

        prompt = PromptFormatter.format(state)
        return await self.provider.chat(prompt, responder_name=state.responder_name)
