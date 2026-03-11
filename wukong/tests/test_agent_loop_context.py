"""
Tests for AgentLoop context integration.

Tests the context resolution in AgentLoop when CLI passes mentions.

Run with: pytest tests/test_agent_loop_context.py -v
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from wukong.core.agent.loop import AgentLoop, MentionInput
from wukong.core.context import (
    ContextItem,
    ContextRegistry,
    FileProvider,
)
from wukong.core.session.models import Session
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
        (workspace / "utils.py").write_text(
            "def helper():\n    return 42\n",
            encoding="utf-8"
        )
        
        yield workspace


@pytest.fixture
def mock_llm():
    """Create a mock LLM that returns a simple response."""
    llm = MagicMock()
    
    async def mock_stream(*args, **kwargs):
        # Yield a simple response
        chunk = MagicMock()
        chunk.content = "这是 LLM 的回复"
        chunk.reasoning_content = None
        chunk.tool_calls = None
        yield chunk
    
    llm.stream_chat = mock_stream
    return llm


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
    """Create a registry with FileProvider (stateless)."""
    reg = ContextRegistry()
    reg.register(FileProvider())  # No workspace_dir in constructor
    return reg


# ========================================
# Test _resolve_context
# ========================================

class TestResolveContext:
    """Test _resolve_context method."""
    
    @pytest.mark.asyncio
    async def test_empty_mentions_returns_empty(
        self,
        mock_llm,
        session,
        mock_session_manager,
        context_registry,
    ):
        """Test that empty mentions list returns empty context."""
        loop = AgentLoop(
            llm=mock_llm,
            session=session,
            session_manager=mock_session_manager,
            context_registry=context_registry,
        )
        
        context_items = await loop._resolve_context([])
        
        assert context_items == []
    
    @pytest.mark.asyncio
    async def test_single_file_mention(
        self,
        mock_llm,
        session,
        mock_session_manager,
        context_registry,
    ):
        """Test resolving a single @file mention."""
        loop = AgentLoop(
            llm=mock_llm,
            session=session,
            session_manager=mock_session_manager,
            context_registry=context_registry,
        )
        
        mentions = [MentionInput(provider="file", query="main.py")]
        context_items = await loop._resolve_context(mentions)
        
        assert len(context_items) == 1
        assert context_items[0].provider == "file"
        assert "def main():" in context_items[0].content
    
    @pytest.mark.asyncio
    async def test_multiple_file_mentions(
        self,
        mock_llm,
        session,
        mock_session_manager,
        context_registry,
    ):
        """Test resolving multiple @file mentions."""
        loop = AgentLoop(
            llm=mock_llm,
            session=session,
            session_manager=mock_session_manager,
            context_registry=context_registry,
        )
        
        mentions = [
            MentionInput(provider="file", query="main.py"),
            MentionInput(provider="file", query="utils.py"),
        ]
        context_items = await loop._resolve_context(mentions)
        
        assert len(context_items) == 2
        
        # Check contents
        contents = [item.content for item in context_items]
        assert any("def main():" in c for c in contents)
        assert any("def helper():" in c for c in contents)
    
    @pytest.mark.asyncio
    async def test_unknown_provider_ignored(
        self,
        mock_llm,
        session,
        mock_session_manager,
        context_registry,
    ):
        """Test that unknown provider mentions are ignored."""
        loop = AgentLoop(
            llm=mock_llm,
            session=session,
            session_manager=mock_session_manager,
            context_registry=context_registry,
        )
        
        mentions = [
            MentionInput(provider="unknown", query="something"),
            MentionInput(provider="file", query="main.py"),
        ]
        context_items = await loop._resolve_context(mentions)
        
        # Only file should be resolved
        assert len(context_items) == 1
        assert context_items[0].provider == "file"
    
    @pytest.mark.asyncio
    async def test_file_not_found_handled_gracefully(
        self,
        mock_llm,
        session,
        mock_session_manager,
        context_registry,
    ):
        """Test that file not found errors are handled gracefully."""
        loop = AgentLoop(
            llm=mock_llm,
            session=session,
            session_manager=mock_session_manager,
            context_registry=context_registry,
        )
        
        # Request non-existent file
        mentions = [MentionInput(provider="file", query="nonexistent.py")]
        context_items = await loop._resolve_context(mentions)
        
        # Should not crash, just return empty context
        assert context_items == []


# ========================================
# Test run() with context
# ========================================

class TestRunWithContext:
    """Test run() method with context integration."""
    
    @pytest.mark.asyncio
    async def test_run_with_mentions(
        self,
        mock_llm,
        session,
        mock_session_manager,
        context_registry,
    ):
        """Test run() with mentions passed from CLI."""
        loop = AgentLoop(
            llm=mock_llm,
            session=session,
            session_manager=mock_session_manager,
            context_registry=context_registry,
        )
        
        mentions = [MentionInput(provider="file", query="main.py")]
        
        # Collect response
        response = ""
        async for chunk in loop.run("解释这个文件", mentions=mentions):
            if chunk.content:
                response += chunk.content
        
        assert response == "这是 LLM 的回复"
        
        # Check that context was added to history
        messages = loop.chat_history.get_messages()
        user_msg = messages[0]
        
        assert len(user_msg.context_items) == 1
        assert user_msg.context_items[0].provider == "file"
        # Clean text should be stored
        assert user_msg.message.content == "解释这个文件"
    
    @pytest.mark.asyncio
    async def test_run_without_mentions(
        self,
        mock_llm,
        session,
        mock_session_manager,
        context_registry,
    ):
        """Test run() without any mentions."""
        loop = AgentLoop(
            llm=mock_llm,
            session=session,
            session_manager=mock_session_manager,
            context_registry=context_registry,
        )
        
        response = ""
        async for chunk in loop.run("你好"):
            if chunk.content:
                response += chunk.content
        
        assert response == "这是 LLM 的回复"
        
        # Check no context was added
        messages = loop.chat_history.get_messages()
        user_msg = messages[0]
        
        assert len(user_msg.context_items) == 0
        assert user_msg.message.content == "你好"
    
    @pytest.mark.asyncio
    async def test_run_with_none_mentions(
        self,
        mock_llm,
        session,
        mock_session_manager,
        context_registry,
    ):
        """Test run() with mentions=None (same as empty)."""
        loop = AgentLoop(
            llm=mock_llm,
            session=session,
            session_manager=mock_session_manager,
            context_registry=context_registry,
        )
        
        response = ""
        async for chunk in loop.run("你好", mentions=None):
            if chunk.content:
                response += chunk.content
        
        assert response == "这是 LLM 的回复"
        
        # Check no context was added
        messages = loop.chat_history.get_messages()
        user_msg = messages[0]
        
        assert len(user_msg.context_items) == 0


# ========================================
# Test Global Registry
# ========================================

class TestGlobalRegistry:
    """Test using global registry when none provided."""
    
    @pytest.mark.asyncio
    async def test_uses_global_registry_when_none_provided(
        self,
        mock_llm,
        session,
        mock_session_manager,
    ):
        """Test that global registry is used when none provided."""
        # Don't pass registry - should use global
        loop = AgentLoop(
            llm=mock_llm,
            session=session,
            session_manager=mock_session_manager,
            # No registry param - uses get_registry()
        )
        
        # The global registry should have FileProvider
        assert loop._context_registry is not None
        assert loop._context_registry.has("file")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
