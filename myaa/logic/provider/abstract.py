from abc import ABC, abstractmethod
from myaa.domain.message import Message
from myaa.logic.formatter.prompt_formatter import LLMPrompt


class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, prompt: LLMPrompt, responder_id: str) -> Message: ...
