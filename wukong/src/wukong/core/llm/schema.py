from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

# 消息角色定义
Role = Literal["system", "user", "assistant", "tool"]

class FunctionDefinition(BaseModel):
    """OpenAI 风格的消息函数定义"""
    name: str
    description: Optional[str] = None
    parameters: Dict[str, Any]  # JSON Schema 格式

class ToolDefinition(BaseModel):
    """OpenAI 风格的工具定义"""
    type: Literal["function"] = "function"
    function: FunctionDefinition

class FunctionCall(BaseModel):
    """LLM 返回的函数调用详细信息"""
    name: str
    arguments: str  # 注意：LLM 返回的是 JSON 字符串

class ToolCall(BaseModel):
    """LLM 返回的工具调用对象"""
    id: str
    type: Literal["function"] = "function"
    function: FunctionCall

class ChatMessage(BaseModel):
    """
    统一的聊天消息模型。
    完全兼容 OpenAI 消息结构。
    """
    role: Role
    content: Optional[str] = None
    reasoning_content: Optional[str] = None  # 模型思考过程
    
    # 工具调用列表 (assistant 角色时使用)
    tool_calls: Optional[List[ToolCall]] = None
    
    # 工具响应相关字段 (tool 角色时使用)
    tool_call_id: Optional[str] = None
    name: Optional[str] = None  # 工具名称

class LLMResponse(BaseModel):
    """
    统一的 LLM 响应结果。
    """
    content: Optional[str] = None
    reasoning_content: Optional[str] = None  # 模型思考过程（DeepSeek/OpenAI O1 等支持）
    tool_calls: Optional[List[ToolCall]] = None
    
    # Token 统计
    usage: Dict[str, int] = Field(
        default_factory=lambda: {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    )
    
    # 原始响应数据（用于调试）
    raw_response: Any = None
