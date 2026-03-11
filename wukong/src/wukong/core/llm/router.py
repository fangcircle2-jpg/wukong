from typing import Dict, Type, Any

from ..config.settings import Settings, get_settings
from .base import BaseLLM


class LLMProviderError(Exception):
    """当 LLM 提供商配置错误或未实现时抛出"""
    pass


def get_llm_backend(settings: Settings | None = None) -> BaseLLM:
    """
    LLM 后端工厂函数。
    根据配置实例化并返回对应的 LLM 适配器。
    
    Note: Adapters are imported lazily to avoid loading optional dependencies
    (like 'openai') when not needed.
    """
    if settings is None:
        settings = get_settings()
        
    provider = settings.llm.provider.lower()
    
    # 基础通用参数
    common_args: Dict[str, Any] = {
        "model": settings.llm.model,
        "temperature": settings.llm.temperature,
        "max_tokens": settings.llm.max_tokens,
    }
    
    try:
        if provider == "openai":
            from .adapters.openai import OpenAILLM
            return OpenAILLM(
                api_key=settings.llm.openai_api_key,
                base_url=settings.llm.openai_base_url,
                **common_args
            )
            
        elif provider == "mock":
            from .adapters.mock import MockLLM
            return MockLLM(**common_args)
            
        elif provider == "local":
            # 本地模型通常使用 OpenAI 兼容协议
            from .adapters.openai import OpenAILLM
            return OpenAILLM(
                api_key="not-needed", # 本地通常不需要 API Key
                base_url=settings.llm.local_base_url,
                model=settings.llm.local_model,
                temperature=settings.llm.temperature,
                max_tokens=settings.llm.max_tokens,
            )
            
        elif provider == "anthropic":
            # 暂时未实现，抛出明确错误
            raise LLMProviderError(
                f"Provider '{provider}' is planned but not yet implemented. "
                "Please use 'openai' or 'local' for now."
            )
            
        else:
            raise LLMProviderError(
                f"Unknown LLM provider: '{provider}'. "
                "Supported providers are: openai, local, anthropic, google."
            )
            
    except Exception as e:
        if isinstance(e, LLMProviderError):
            raise e
        raise LLMProviderError(f"Failed to initialize LLM provider '{provider}': {str(e)}") from e

