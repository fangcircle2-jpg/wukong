"""
Tests for AgentLoop tool system integration.

Tests the tool execution flow in AgentLoop when LLM requests tool calls.

Run with: pytest tests/test_agent_loop_tools.py -v
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from wukong.core.agent.loop import AgentLoop, MentionInput
from wukong.core.context import ContextRegistry, FileProvider
from wukong.core.llm.schema import ChatMessage, FunctionCall, LLMResponse, ToolCall
from wukong.core.session.models import Session
from wukong.core.tools import ToolRegistry, get_registry
from wukong.core.tools.base import Tool, ToolResult
from wukong.core.tools.builtins import ReadFileTool
from wukong.core.utils.id import generate_project_id


# ========================================
# Fixtures
# ========================================

@pytest.fixture
def temp_workspace():
    """Create a temporary workspace with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        
        # Create test files
        (workspace / "main.py").write_text(
            "def main():\n    print('Hello')\n",
            encoding="utf-8"
        )
        (workspace / "test.txt").write_text(
            "This is a test file.\nLine 2.\nLine 3.",
            encoding="utf-8"
        )
        
        yield workspace


@pytest.fixture
def mock_session_manager():
    """Create a mock session manager."""
    manager = MagicMock()
    manager.save_session = MagicMock()
    return manager


@pytest.fixture
def session(temp_workspace):
    """Create a test session."""
    return Session(
        session_id="test-session",
        project_id=generate_project_id(temp_workspace),
        title="Test Session",
        workspace_directory=str(temp_workspace),
    )


@pytest.fixture
def context_registry():
    """Create a registry with FileProvider."""
    reg = ContextRegistry()
    reg.register(FileProvider())
    return reg


@pytest.fixture
def tool_registry():
    """Create a tool registry with default tools."""
    reg = ToolRegistry()
    reg.register_defaults()
    return reg


# ========================================
# Mock LLM Helpers
# ========================================

def create_mock_llm_no_tools():
    """Create a mock LLM that returns a simple response without tool calls."""
    llm = MagicMock()
    
    async def mock_stream(*args, **kwargs):
        chunk = MagicMock()
        chunk.content = "这是 LLM 的回复"
        chunk.reasoning_content = None
        chunk.tool_calls = None
        yield chunk
    
    llm.stream_chat = mock_stream
    return llm


def create_mock_llm_with_tool_call(tool_name: str, arguments: dict):
    """Create a mock LLM that returns a tool call then final response."""
    llm = MagicMock()
    call_count = [0]  # Use list to allow mutation in closure
    
    async def mock_stream(*args, **kwargs):
        call_count[0] += 1
        
        if call_count[0] == 1:
            # First call: return tool call
            chunk = MagicMock()
            chunk.content = ""
            chunk.reasoning_content = None
            chunk.tool_calls = [
                ToolCall(
                    id="call_123",
                    type="function",
                    function=FunctionCall(
                        name=tool_name,
                        arguments=json.dumps(arguments),
                    ),
                )
            ]
            yield chunk
        else:
            # Second call: return final response
            chunk = MagicMock()
            chunk.content = "工具执行完成，这是最终回复"
            chunk.reasoning_content = None
            chunk.tool_calls = None
            yield chunk
    
    llm.stream_chat = mock_stream
    return llm


# ========================================
# Test Tool Registry Integration
# ========================================

class TestToolRegistryIntegration:
    """Test ToolRegistry integration in AgentLoop."""
    
    def test_uses_provided_tool_registry(
        self,
        session,
        mock_session_manager,
        context_registry,
        tool_registry,
    ):
        """Test that provided tool registry is used."""
        llm = create_mock_llm_no_tools()
        
        loop = AgentLoop(
            llm=llm,
            session=session,
            session_manager=mock_session_manager,
            context_registry=context_registry,
            tool_registry=tool_registry,
        )
        
        assert loop._tool_registry is tool_registry
        assert "read_file" in loop._tool_registry
    
    def test_uses_global_tool_registry_when_none_provided(
        self,
        session,
        mock_session_manager,
        context_registry,
    ):
        """Test that global tool registry is used when none provided."""
        llm = create_mock_llm_no_tools()
        
        loop = AgentLoop(
            llm=llm,
            session=session,
            session_manager=mock_session_manager,
            context_registry=context_registry,
            # No tool_registry param - uses global
        )
        
        assert loop._tool_registry is not None
    
    def test_get_definitions_returns_tool_list(
        self,
        session,
        mock_session_manager,
        context_registry,
        tool_registry,
    ):
        """Test that get_definitions returns proper tool definitions."""
        llm = create_mock_llm_no_tools()
        
        loop = AgentLoop(
            llm=llm,
            session=session,
            session_manager=mock_session_manager,
            context_registry=context_registry,
            tool_registry=tool_registry,
        )
        
        definitions = loop._tool_registry.get_definitions()
        
        assert len(definitions) > 0
        assert all(d.type == "function" for d in definitions)
        
        # Check read_file is in definitions
        names = [d.function.name for d in definitions]
        assert "read_file" in names


# ========================================
# Test Tool Execution
# ========================================

class TestToolExecution:
    """Test tool execution in AgentLoop."""
    
    @pytest.mark.asyncio
    async def test_execute_read_file_tool(
        self,
        temp_workspace,
        session,
        mock_session_manager,
        context_registry,
        tool_registry,
    ):
        """Test executing read_file tool."""
        llm = create_mock_llm_with_tool_call(
            "read_file",
            {"path": "test.txt"},
        )
        
        loop = AgentLoop(
            llm=llm,
            session=session,
            session_manager=mock_session_manager,
            context_registry=context_registry,
            tool_registry=tool_registry,
        )
        
        # Run and collect responses
        responses = []
        async for chunk in loop.run("读取 test.txt 文件"):
            if chunk.content:
                responses.append(chunk.content)
        
        # Should have tool result and final response
        assert len(responses) >= 2
        
        # Check tool result contains file content
        # New format: [Tool: name|success|duration|args_json]\ncontent
        tool_response = responses[0]
        assert tool_response.startswith("[Tool: read_file|")
        assert "This is a test file" in tool_response
    
    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(
        self,
        session,
        mock_session_manager,
        context_registry,
        tool_registry,
    ):
        """Test executing a tool that doesn't exist."""
        llm = create_mock_llm_with_tool_call(
            "nonexistent_tool",
            {"arg": "value"},
        )
        
        loop = AgentLoop(
            llm=llm,
            session=session,
            session_manager=mock_session_manager,
            context_registry=context_registry,
            tool_registry=tool_registry,
        )
        
        # Run and collect responses
        responses = []
        async for chunk in loop.run("执行不存在的工具"):
            if chunk.content:
                responses.append(chunk.content)
        
        # Should have error response
        tool_response = responses[0]
        assert "not found" in tool_response.lower()
    
    @pytest.mark.asyncio
    async def test_execute_tool_with_invalid_arguments(
        self,
        session,
        mock_session_manager,
        context_registry,
        tool_registry,
    ):
        """Test executing a tool with invalid JSON arguments."""
        llm = MagicMock()
        call_count = [0]
        
        async def mock_stream(*args, **kwargs):
            call_count[0] += 1
            
            if call_count[0] == 1:
                chunk = MagicMock()
                chunk.content = ""
                chunk.reasoning_content = None
                # Create tool call with invalid JSON
                tool_call = MagicMock()
                tool_call.id = "call_456"
                tool_call.function = MagicMock()
                tool_call.function.name = "read_file"
                tool_call.function.arguments = "not valid json"
                chunk.tool_calls = [tool_call]
                yield chunk
            else:
                chunk = MagicMock()
                chunk.content = "处理完成"
                chunk.reasoning_content = None
                chunk.tool_calls = None
                yield chunk
        
        llm.stream_chat = mock_stream
        
        loop = AgentLoop(
            llm=llm,
            session=session,
            session_manager=mock_session_manager,
            context_registry=context_registry,
            tool_registry=tool_registry,
        )
        
        # Should not crash
        responses = []
        async for chunk in loop.run("测试无效参数"):
            if chunk.content:
                responses.append(chunk.content)
        
        # Should have error in response
        assert any("invalid" in r.lower() or "error" in r.lower() for r in responses)


# ========================================
# Test Tool Call States Conversion
# ========================================

class TestToolCallStateConversion:
    """Test conversion between ToolCall and ToolCallState."""
    
    def test_convert_to_tool_call_states(
        self,
        session,
        mock_session_manager,
        context_registry,
        tool_registry,
    ):
        """Test converting ToolCall to ToolCallState."""
        llm = create_mock_llm_no_tools()
        
        loop = AgentLoop(
            llm=llm,
            session=session,
            session_manager=mock_session_manager,
            context_registry=context_registry,
            tool_registry=tool_registry,
        )
        
        tool_calls = [
            ToolCall(
                id="call_abc",
                type="function",
                function=FunctionCall(
                    name="read_file",
                    arguments='{"path": "test.py"}',
                ),
            ),
        ]
        
        states = loop._convert_to_tool_call_states(tool_calls)
        
        assert len(states) == 1
        assert states[0].tool_call_id == "call_abc"
        assert states[0].tool_name == "read_file"
        assert states[0].arguments == {"path": "test.py"}
    
    def test_convert_states_to_tool_calls(
        self,
        session,
        mock_session_manager,
        context_registry,
        tool_registry,
    ):
        """Test converting ToolCallState back to ToolCall."""
        from wukong.core.session.models import ToolCallState, ToolStatus
        
        llm = create_mock_llm_no_tools()
        
        loop = AgentLoop(
            llm=llm,
            session=session,
            session_manager=mock_session_manager,
            context_registry=context_registry,
            tool_registry=tool_registry,
        )
        
        states = [
            ToolCallState(
                tool_call_id="call_xyz",
                tool_name="write_file",
                arguments={"path": "out.txt", "content": "hello"},
                status=ToolStatus.DONE,
            ),
        ]
        
        tool_calls = loop._convert_states_to_tool_calls(states)
        
        assert len(tool_calls) == 1
        assert tool_calls[0].id == "call_xyz"
        assert tool_calls[0].function.name == "write_file"
        assert json.loads(tool_calls[0].function.arguments) == {
            "path": "out.txt",
            "content": "hello",
        }


# ========================================
# Test History Updates
# ========================================

class TestHistoryUpdates:
    """Test that history is correctly updated during tool execution."""
    
    @pytest.mark.asyncio
    async def test_history_contains_tool_calls(
        self,
        temp_workspace,
        session,
        mock_session_manager,
        context_registry,
        tool_registry,
    ):
        """Test that tool calls are recorded in history."""
        llm = create_mock_llm_with_tool_call(
            "read_file",
            {"path": "test.txt"},
        )
        
        loop = AgentLoop(
            llm=llm,
            session=session,
            session_manager=mock_session_manager,
            context_registry=context_registry,
            tool_registry=tool_registry,
        )
        
        # Run
        async for _ in loop.run("读取文件"):
            pass
        
        # Check history
        messages = loop.chat_history.get_messages()
        
        # Should have: user, assistant (with tool calls), tool result, assistant (final)
        assert len(messages) >= 3
        
        # Check user message
        assert messages[0].message.role == "user"
        
        # Check assistant message has tool call states
        assistant_msg = messages[1]
        assert assistant_msg.message.role == "assistant"
        assert len(assistant_msg.tool_call_states) > 0
        
        # Check tool result message
        tool_msg = messages[2]
        assert tool_msg.message.role == "tool"
        assert tool_msg.message.tool_call_id is not None


# ========================================
# Test No Tool Calls
# ========================================

class TestNoToolCalls:
    """Test behavior when LLM doesn't request tools."""
    
    @pytest.mark.asyncio
    async def test_run_without_tool_calls(
        self,
        session,
        mock_session_manager,
        context_registry,
        tool_registry,
    ):
        """Test run() when LLM doesn't use tools."""
        llm = create_mock_llm_no_tools()
        
        loop = AgentLoop(
            llm=llm,
            session=session,
            session_manager=mock_session_manager,
            context_registry=context_registry,
            tool_registry=tool_registry,
        )
        
        responses = []
        async for chunk in loop.run("你好"):
            if chunk.content:
                responses.append(chunk.content)
        
        assert len(responses) == 1
        assert responses[0] == "这是 LLM 的回复"
        
        # Check history - should have user and assistant messages
        messages = loop.chat_history.get_messages()
        assert len(messages) == 2
        assert messages[0].message.role == "user"
        assert messages[1].message.role == "assistant"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
