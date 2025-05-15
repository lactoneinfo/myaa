from myaa.data.cache import AgentStateCache
from myaa.logic.domain.message import Message
from myaa.logic.formatter.prompt_formatter import PromptFormatter


class ChatAgent:
    def __init__(self, cache: AgentStateCache):
        self.cache = cache

    async def generate(self, as_id: str) -> Message:
        state = await self.cache.get(as_id)
        assert state is not None, f"AgentState not found for {as_id}"

        prompt = PromptFormatter.format(state)

        prompt_text = "\n".join(f"[{m['role']}] {m['content']}" for m in prompt)

        return Message(
            speaker=state.character_name,
            content=f"{prompt_text}",
        )
