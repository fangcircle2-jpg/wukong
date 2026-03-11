from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Optional
from .schema import ChatMessage, LLMResponse, ToolDefinition

class BaseLLM(ABC):
    """
    LLM 适配器抽象基类。
    所有具体的 LLM 提供商（OpenAI, Anthropic, Gemini 等）都必须继承此类。
    """
    
    def __init__(self, model: str, temperature: float = 0.7, max_tokens: int = 4096):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    @abstractmethod
    async def chat(
        self, 
        messages: List[ChatMessage], 
        tools: Optional[List[ToolDefinition]] = None
    ) -> LLMResponse:
        """
        非流式对话。
        
        Args:
            messages: 对话历史记录列表。
            tools: 工具定义列表（OpenAI 格式）。
        """
        pass

    @abstractmethod
    async def stream_chat(
        self, 
        messages: List[ChatMessage], 
        tools: Optional[List[ToolDefinition]] = None
    ) -> AsyncIterator[LLMResponse]:
        """
        流式对话。
        """
        pass
