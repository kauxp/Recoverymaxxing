from app.config import settings
from app.llm.base import LLMProvider
from app.llm.gemini import GeminiProvider
from app.llm.openai import OpenAIProvider
from app.llm.claude import ClaudeProvider


class LLMFactory:

    @staticmethod
    def create() -> LLMProvider:

        provider = settings.LLM_PROVIDER

        if provider == "gemini":
            return GeminiProvider()

        if provider == "openai":
            return OpenAIProvider()

        if provider == "claude":
            return ClaudeProvider()

        raise ValueError(
            f"Unsupported LLM provider: {provider}"
        )