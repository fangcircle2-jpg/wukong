import asyncio
from typing import AsyncIterator, List, Optional, Dict, Any
from ..base import BaseLLM
from ..schema import ChatMessage, LLMResponse, ToolDefinition, ToolCall, FunctionCall

class MockLLM(BaseLLM):
    """
    模拟 LLM 适配器。
    用于在没有 API Key 或网络环境的情况下测试系统流程。
    """
    
    async def chat(
        self, 
        messages: List[ChatMessage], 
        tools: Optional[List[ToolDefinition]] = None
    ) -> LLMResponse:
        """模拟非流式返回"""
        last_msg = messages[-1].content.lower() if messages[-1].content else ""
        
        # 模拟工具调用逻辑
        if "天气" in last_msg and tools:
            tool_calls = [
                ToolCall(
                    id="mock_call_123",
                    type="function",
                    function=FunctionCall(name="get_weather", arguments='{"location": "北京"}')
                )
            ]
            return LLMResponse(content=None, tool_calls=tool_calls)
        
        # 模拟普通文本返回
        return LLMResponse(
            content=f"这是一个模拟回复。你刚才说的是：'{last_msg}'",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        )

    async def stream_chat(
        self, 
        messages: List[ChatMessage], 
        tools: Optional[List[ToolDefinition]] = None
    ) -> AsyncIterator[LLMResponse]:
        """模拟流式返回"""
        full_text = f"这是模拟的流式回复。很高兴为您服务！"
        
        for char in full_text:
            await asyncio.sleep(0.01)  # 模拟一点网络延迟
            yield LLMResponse(content=char)

