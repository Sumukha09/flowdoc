
from app.config import get_settings


def get_llm():
    """Return the configured LLM adapter."""
    settings = get_settings()
    provider = settings.llm_provider.lower()
    
    if provider == "mock":
        from app.llm.mock import MockLLMAdapter
        return MockLLMAdapter()
    else:
        from app.llm.gemini import GeminiLLMAdapter
        return GeminiLLMAdapter()
