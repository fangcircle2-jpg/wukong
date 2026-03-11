"""
LLM module - Multi-provider LLM adapters and router.

Note: OpenAILLM and other adapters are lazy-loaded to avoid importing
optional dependencies (like 'openai') when not needed.
"""

from .base import BaseLLM
from .schema import ChatMessage, LLMResponse, ToolDefinition, ToolCall, FunctionCall
from .router import get_llm_backend, LLMProviderError


def __getattr__(name: str):
    """Lazy load adapters to avoid importing optional dependencies."""
    if name == "OpenAILLM":
        from .adapters import OpenAILLM
        return OpenAILLM
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BaseLLM",
    "ChatMessage",
    "LLMResponse",
    "ToolDefinition",
    "ToolCall",
    "FunctionCall",
    "OpenAILLM",
    "get_llm_backend",
    "LLMProviderError",
]
