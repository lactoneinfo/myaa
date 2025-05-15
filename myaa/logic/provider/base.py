import os
from myaa.logic.provider.gemini_provider import GeminiProvider

from myaa.logic.provider.abstract import LLMProvider


def get_provider() -> LLMProvider:
    provider = os.getenv("LLM_PROVIDER")
    if provider == "gemini":

        return GeminiProvider()
    else:
        raise ValueError(f"Unsupported LLM provider: '{provider}'")
