"""
LLM adapters module.

Note: Adapters are lazy-loaded to avoid importing optional dependencies
(like 'openai') when not needed.
"""

from .mock import MockLLM


def __getattr__(name: str):
    """Lazy load adapters with optional dependencies."""
    if name == "OpenAILLM":
        from .openai import OpenAILLM
        return OpenAILLM
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["OpenAILLM", "MockLLM"]
