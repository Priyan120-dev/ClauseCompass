"""LLM package entry point and factory function."""
from app.config import settings
from app.llm.base import LLMClient
from app.llm.fake import FakeLLMClient


def get_llm_client() -> LLMClient:
    """Return configured LLM client: GeminiClient if key present & not demo_mode, else FakeLLMClient."""
    if not settings.is_demo_mode:
        try:
            from app.llm.gemini import GeminiClient
            return GeminiClient()
        except Exception:
            # Fallback gracefully to FakeLLMClient
            return FakeLLMClient()
    return FakeLLMClient()
