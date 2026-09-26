"""LLM package entry point and factory function."""
from app.config import settings
from app.llm.base import LLMClient
from app.llm.fake import FakeLLMClient

_cached_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Return configured LLM client: GeminiClient if key present & not demo_mode, else FakeLLMClient."""
    global _cached_client
    if _cached_client is not None:
        return _cached_client

    if not settings.is_demo_mode:
        try:
            from app.llm.gemini import GeminiClient
            _cached_client = GeminiClient()
            return _cached_client
        except Exception:
            # Fallback gracefully to FakeLLMClient
            _cached_client = FakeLLMClient()
            return _cached_client
    _cached_client = FakeLLMClient()
    return _cached_client
