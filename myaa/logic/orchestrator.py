from __future__ import annotations
from myaa.data.cache import AgentStateCache
from myaa.logic.input_manager import InputManager
from myaa.logic.chat_agent import ChatAgent
from myaa.logic.output_manager import OutputManager


class Orchestrator:
    def __init__(self, cache: AgentStateCache):
        self.input = InputManager(cache)
        self.chat = ChatAgent(cache)
        self.output = OutputManager(cache)

    async def run(self, session_key: str, text: str) -> str:
        as_id = await self.input.handle(session_key, text)
        reply = await self.chat.generate(as_id)
        await self.output.finalize(as_id, reply)
        return reply
