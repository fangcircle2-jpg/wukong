from typing import AsyncIterator, List, Optional, Dict, Any
from openai import AsyncOpenAI
from ..base import BaseLLM
from ..schema import ChatMessage, LLMResponse, ToolDefinition, ToolCall, FunctionCall

class OpenAILLM(BaseLLM):
    """
    OpenAI 适配器实现。
    支持所有兼容 OpenAI API 协议的模型（包括 DeepSeek, Groq, Ollama 等）。
    """
    
    def __init__(
        self, 
        model: str = "glm-4.7", 
        api_key: str = "",
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ):
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    def _convert_messages(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        """将内部 ChatMessage 转换为 OpenAI API 字典格式"""
        openai_msgs = []
        for msg in messages:
            m = {"role": msg.role}
            if msg.content is not None:
                m["content"] = msg.content
            
            # 处理 Assistant 的工具调用
            if msg.role == "assistant" and msg.tool_calls:
                m["tool_calls"] = [tc.model_dump() for tc in msg.tool_calls]
            
            # 处理 Tool 角色的响应
            if msg.role == "tool":
                m["tool_call_id"] = msg.tool_call_id
                
            openai_msgs.append(m)
        return openai_msgs

    def _convert_tools(self, tools: Optional[List[ToolDefinition]]) -> Optional[List[Dict[str, Any]]]:
        """将内部 ToolDefinition 转换为 OpenAI 工具字典"""
        if not tools:
            return None
        return [t.model_dump() for t in tools]

    async def chat(
        self, 
        messages: List[ChatMessage], 
        tools: Optional[List[ToolDefinition]] = None
    ) -> LLMResponse:
        """非流式对话实现"""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=self._convert_messages(messages),
            tools=self._convert_tools(tools),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        
        choice = response.choices[0].message
        
        # 转换工具调用
        tool_calls = None
        if choice.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    type="function",
                    function=FunctionCall(
                        name=tc.function.name,
                        arguments=tc.function.arguments
                    )
                ) for tc in choice.tool_calls
            ]
        
        # 获取思考过程内容 (DeepSeek 支持 reasoning_content, OpenAI O1 暂不支持流式获取)
        reasoning_content = getattr(choice, "reasoning_content", None)
            
        return LLMResponse(
            content=choice.content,
            reasoning_content=reasoning_content,
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            raw_response=response
        )

    async def stream_chat(
        self, 
        messages: List[ChatMessage], 
        tools: Optional[List[ToolDefinition]] = None
    ) -> AsyncIterator[LLMResponse]:
        """流式对话实现"""
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=self._convert_messages(messages),
            tools=self._convert_tools(tools),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True
        )
        
        async for chunk in stream:
            if not chunk.choices:
                continue
                
            delta = chunk.choices[0].delta
            
            # 处理工具调用片段 (OpenAI 流式返回中工具参数是 delta 增量)
            tool_calls = None
            if delta.tool_calls:
                tool_calls = []
                for tc_delta in delta.tool_calls:
                    # 注意：在流式的第一个片段中包含 ID 和 Name，后续片段只包含 Arguments
                    tool_calls.append(ToolCall(
                        id=tc_delta.id or "", # 只有第一块有 ID
                        type="function",
                        function=FunctionCall(
                            name=tc_delta.function.name or "",
                            arguments=tc_delta.function.arguments or ""
                        )
                    ))
            
            yield LLMResponse(
                content=delta.content,
                reasoning_content=getattr(delta, "reasoning_content", None),
                tool_calls=tool_calls,
                raw_response=chunk
            )

