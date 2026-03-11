import asyncio
from typing import AsyncIterator, List, Optional, Dict, Any
from ..base import BaseLLM
from ..schema import ChatMessage, LLMResponse, ToolDefinition, ToolCall, FunctionCall

class MockLLM(BaseLLM):
    """
    Mock LLM adapter.
    Used for testing system flow without API keys or network.
    """
    
    async def chat(
        self, 
        messages: List[ChatMessage], 
        tools: Optional[List[ToolDefinition]] = None
    ) -> LLMResponse:
        """Mock non-streaming response."""
        last_msg = messages[-1].content.lower() if messages[-1].content else ""
        
        # Mock tool call logic
        if "weather" in last_msg and tools:
            tool_calls = [
                ToolCall(
                    id="mock_call_123",
                    type="function",
                    function=FunctionCall(name="get_weather", arguments='{"location": "Beijing"}')
                )
            ]
            return LLMResponse(content=None, tool_calls=tool_calls)
        
        # Mock plain text response
        return LLMResponse(
            content=f"This is a mock response. You said: '{last_msg}'",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        )

    async def stream_chat(
        self, 
        messages: List[ChatMessage], 
        tools: Optional[List[ToolDefinition]] = None
    ) -> AsyncIterator[LLMResponse]:
        """Mock streaming response."""
        full_text = "This is a mock streaming response. Happy to help!"
        
        for char in full_text:
            await asyncio.sleep(0.01)  # Simulate network delay
            yield LLMResponse(content=char)

