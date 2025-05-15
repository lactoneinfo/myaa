import os
from abc import ABC, abstractmethod
from myaa.logic.domain.message import Message
from myaa.logic.formatter.prompt_formatter import LLMPrompt
from myaa.logic.provider.gemini_provider import GeminiProvider


class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, prompt: LLMPrompt, character_name: str) -> Message:
        pass


def get_provider() -> LLMProvider:
    provider = os.getenv("LLM_PROVIDER")
    if provider == "gemini":

        return GeminiProvider()
    else:
        raise ValueError(f"Unsupported LLM provider: '{provider}'")
