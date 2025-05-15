from abc import ABC, abstractmethod
from myaa.logic.domain.message import Message
from myaa.logic.formatter.prompt_formatter import LLMPrompt


class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, prompt: LLMPrompt, responder_name: str) -> Message: ...
