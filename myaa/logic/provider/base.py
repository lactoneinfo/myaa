import os
from abc import ABC, abstractmethod
from myaa.logic.domain.message import Message
from myaa.logic.formatter.prompt_formatter import LLMPrompt


class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, prompt: LLMPrompt, character_name: str) -> Message:
        pass


def get_provider() -> LLMProvider:
    provider = os.getenv("LLM_PROVIDER")
    if provider == "gemini":
        from .gemini_provider import GeminiProvider

        return GeminiProvider()
    else:
        raise ValueError(f"Unsupported LLM provider: '{provider}'")
