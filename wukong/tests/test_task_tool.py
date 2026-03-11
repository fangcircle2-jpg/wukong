"""
Tests for TaskTool and AgentConfigLoader.

Run with: pytest tests/test_task_tool.py -v
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from wukong.core.agent.config import AgentConfig, AgentConfigLoader, DEFAULT_AGENTS
from wukong.core.tools.builtins.task import (
    TaskParams,
    TaskTool,
    TaskMetadata,
    ToolCallSummary,
)


# ========================================
# AgentConfig Tests
# ========================================

class TestAgentConfig:
    """Tests for AgentConfig model."""
    
    def test_create_subagent_config(self):
        """Test creating a subagent configuration."""
        config = AgentConfig(
            name="test-agent",
            mode="subagent",
            description="Test agent",
            tools=["read_file", "grep"],
        )
        
        assert config.name == "test-agent"
        assert config.mode == "subagent"
        assert config.is_subagent()
        assert not config.is_primary()
        assert "read_file" in config.tools
    
    def test_create_primary_config(self):
        """Test creating a primary agent configuration."""
        config = AgentConfig(
            name="main-agent",
            mode="primary",
            description="Main agent",
        )
        
        assert config.is_primary()
        assert not config.is_subagent()
    
    def test_default_values(self):
        """Test default values for optional fields."""
        config = AgentConfig(name="minimal")
        
        assert config.mode == "subagent"
        assert config.description == ""
        assert config.model is None
        assert config.tools == []
        assert config.prompt == ""
        assert config.temperature is None
        assert config.max_steps is None


class TestAgentConfigLoader:
    """Tests for AgentConfigLoader."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_load_from_defaults(self, temp_workspace):
        """Test loading built-in default agents."""
        loader = AgentConfigLoader(temp_workspace)
        
        # Load general agent
        config = loader.load("general")
        assert config is not None
        assert config.name == "general"
        assert config.is_subagent()
        assert "read_file" in config.tools
        
        # Load explore agent
        config = loader.load("explore")
        assert config is not None
        assert config.name == "explore"
        assert config.is_subagent()
        # Explore should not have write tools
        assert "write_file" not in config.tools
    
    def test_load_nonexistent_agent(self, temp_workspace):
        """Test loading a non-existent agent."""
        loader = AgentConfigLoader(temp_workspace)
        
        config = loader.load("nonexistent-agent")
        assert config is None
    
    def test_load_from_yaml_file(self, temp_workspace):
        """Test loading agent from YAML file."""
        # Create agents directory and YAML file
        agents_dir = Path(temp_workspace) / ".wukong" / "agents"
        agents_dir.mkdir(parents=True)
        
        yaml_content = """
name: custom-agent
mode: subagent
description: "Custom test agent"
tools:
  - read_file
  - list_dir
prompt: "You are a custom agent."
max_steps: 5
"""
        (agents_dir / "custom-agent.yaml").write_text(yaml_content)
        
        loader = AgentConfigLoader(temp_workspace)
        config = loader.load("custom-agent")
        
        assert config is not None
        assert config.name == "custom-agent"
        assert config.description == "Custom test agent"
        assert config.tools == ["read_file", "list_dir"]
        assert config.prompt == "You are a custom agent."
        assert config.max_steps == 5
    
    def test_yaml_file_overrides_defaults(self, temp_workspace):
        """Test that YAML file takes precedence over defaults."""
        # Create a YAML file that overrides 'general'
        agents_dir = Path(temp_workspace) / ".wukong" / "agents"
        agents_dir.mkdir(parents=True)
        
        yaml_content = """
name: general
mode: subagent
description: "Overridden general agent"
tools:
  - read_file
"""
        (agents_dir / "general.yaml").write_text(yaml_content)
        
        loader = AgentConfigLoader(temp_workspace)
        config = loader.load("general")
        
        assert config is not None
        assert config.description == "Overridden general agent"
        assert config.tools == ["read_file"]  # Only read_file, not the default list
    
    def test_list_agents(self, temp_workspace):
        """Test listing all available agents."""
        # Create a custom agent file
        agents_dir = Path(temp_workspace) / ".wukong" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "custom.yaml").write_text("name: custom\nmode: subagent")
        
        loader = AgentConfigLoader(temp_workspace)
        agents = loader.list_agents()
        
        # Should include both defaults and custom
        assert "general" in agents
        assert "explore" in agents
        assert "custom" in agents
    
    def test_list_subagents(self, temp_workspace):
        """Test listing only subagent configurations."""
        loader = AgentConfigLoader(temp_workspace)
        subagents = loader.list_subagents()
        
        assert len(subagents) >= 2  # At least general and explore
        for config in subagents:
            assert config.is_subagent()
    
    def test_ensure_agents_dir(self, temp_workspace):
        """Test creating agents directory."""
        loader = AgentConfigLoader(temp_workspace)
        
        # Directory shouldn't exist yet
        assert not loader.agents_dir.exists()
        
        loader.ensure_agents_dir()
        
        assert loader.agents_dir.exists()
        assert loader.agents_dir.is_dir()


# ========================================
# TaskParams Tests
# ========================================

class TestTaskParams:
    """Tests for TaskParams validation."""
    
    def test_valid_params(self):
        """Test valid parameters."""
        params = TaskParams(
            agent="general",
            prompt="Test task",
        )
        
        assert params.agent == "general"
        assert params.prompt == "Test task"
        assert params.model is None
        assert params.timeout == 300000
    
    def test_custom_timeout(self):
        """Test custom timeout."""
        params = TaskParams(
            agent="explore",
            prompt="Quick search",
            timeout=60000,
        )
        
        assert params.timeout == 60000
    
    def test_model_override(self):
        """Test model override."""
        params = TaskParams(
            agent="general",
            prompt="Task",
            model="gpt-4",
        )
        
        assert params.model == "gpt-4"


# ========================================
# TaskTool Tests
# ========================================

class TestTaskTool:
    """Tests for TaskTool."""
    
    @pytest.fixture
    def task_tool(self):
        """Create a TaskTool instance."""
        return TaskTool()
    
    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_tool_metadata(self, task_tool):
        """Test tool metadata."""
        assert task_tool.name == "task"
        assert task_tool.description  # Should have description
        assert task_tool.parameters == TaskParams
    
    @pytest.mark.asyncio
    async def test_missing_session_manager(self, task_tool, temp_workspace):
        """Test error when session_manager is missing."""
        result = await task_tool.execute(
            workspace_dir=temp_workspace,
            agent="general",
            prompt="Test task",
            # session_manager is missing
        )
        
        assert result.success is False
        assert "session_manager" in result.error
    
    @pytest.mark.asyncio
    async def test_missing_parent_session(self, task_tool, temp_workspace):
        """Test error when parent_session is missing."""
        mock_session_manager = MagicMock()
        
        result = await task_tool.execute(
            workspace_dir=temp_workspace,
            agent="general",
            prompt="Test task",
            session_manager=mock_session_manager,
            # parent_session is missing
        )
        
        assert result.success is False
        assert "parent_session" in result.error
    
    @pytest.mark.asyncio
    async def test_missing_llm(self, task_tool, temp_workspace):
        """Test error when llm is missing."""
        mock_session_manager = MagicMock()
        mock_parent_session = MagicMock()
        mock_parent_session.session_id = "ses_parent"
        
        result = await task_tool.execute(
            workspace_dir=temp_workspace,
            agent="general",
            prompt="Test task",
            session_manager=mock_session_manager,
            parent_session=mock_parent_session,
            # llm is missing
        )
        
        assert result.success is False
        assert "llm" in result.error
    
    @pytest.mark.asyncio
    async def test_unknown_agent(self, task_tool, temp_workspace):
        """Test error when agent is not found."""
        mock_session_manager = MagicMock()
        mock_parent_session = MagicMock()
        mock_parent_session.session_id = "ses_parent"
        mock_llm = MagicMock()
        
        result = await task_tool.execute(
            workspace_dir=temp_workspace,
            agent="nonexistent-agent",
            prompt="Test task",
            session_manager=mock_session_manager,
            parent_session=mock_parent_session,
            llm=mock_llm,
        )
        
        assert result.success is False
        assert "not found" in result.error
    
    @pytest.mark.asyncio
    async def test_non_subagent_rejected(self, task_tool, temp_workspace):
        """Test error when trying to invoke non-subagent."""
        # Create a primary agent config
        agents_dir = Path(temp_workspace) / ".wukong" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "primary-test.yaml").write_text(
            "name: primary-test\nmode: primary\ndescription: test"
        )
        
        mock_session_manager = MagicMock()
        mock_parent_session = MagicMock()
        mock_parent_session.session_id = "ses_parent"
        mock_llm = MagicMock()
        
        result = await task_tool.execute(
            workspace_dir=temp_workspace,
            agent="primary-test",
            prompt="Test task",
            session_manager=mock_session_manager,
            parent_session=mock_parent_session,
            llm=mock_llm,
        )
        
        assert result.success is False
        assert "not a subagent" in result.error


class TestTaskToolHelpers:
    """Tests for TaskTool helper methods."""
    
    @pytest.fixture
    def task_tool(self):
        return TaskTool()
    
    def test_extract_final_output_from_assistant_message(self, task_tool):
        """Test extracting final output from history."""
        from wukong.core.session.models import HistoryItem
        from wukong.core.llm.schema import ChatMessage
        
        # Create mock history items
        items = [
            HistoryItem(
                message=ChatMessage(role="user", content="Do something"),
            ),
            HistoryItem(
                message=ChatMessage(role="assistant", content="Here is the result"),
            ),
        ]
        
        output = task_tool._extract_final_output(items)
        assert output == "Here is the result"
    
    def test_extract_final_output_empty_history(self, task_tool):
        """Test extracting output from empty history."""
        output = task_tool._extract_final_output([])
        assert output == ""
    
    def test_extract_tool_summary(self, task_tool):
        """Test extracting tool call summary from history."""
        from wukong.core.session.models import HistoryItem, ToolCallState, ToolStatus
        from wukong.core.llm.schema import ChatMessage
        
        # Create history with tool calls
        items = [
            HistoryItem(
                message=ChatMessage(role="assistant", content=""),
                tool_call_states=[
                    ToolCallState(
                        tool_call_id="tc_001",
                        tool_name="read_file",
                        arguments={"path": "test.py"},
                        status=ToolStatus.DONE,
                    ),
                    ToolCallState(
                        tool_call_id="tc_002",
                        tool_name="grep",
                        arguments={"pattern": "def main"},
                        status=ToolStatus.DONE,
                    ),
                ],
            ),
        ]
        
        summary = task_tool._extract_tool_summary(items)
        
        assert len(summary) == 2
        assert summary[0].tool == "read_file"
        assert summary[0].status == "completed"
        assert summary[1].tool == "grep"
    
    def test_generate_tool_title_read_file(self, task_tool):
        """Test title generation for read_file."""
        from wukong.core.session.models import ToolCallState, ToolStatus
        
        state = ToolCallState(
            tool_call_id="tc_001",
            tool_name="read_file",
            arguments={"path": "/path/to/file.py"},
            status=ToolStatus.DONE,
        )
        
        title = task_tool._generate_tool_title(state)
        assert title == "Read file.py"
    
    def test_generate_tool_title_grep(self, task_tool):
        """Test title generation for grep."""
        from wukong.core.session.models import ToolCallState, ToolStatus
        
        state = ToolCallState(
            tool_call_id="tc_001",
            tool_name="grep",
            arguments={"pattern": "def main"},
            status=ToolStatus.DONE,
        )
        
        title = task_tool._generate_tool_title(state)
        assert "def main" in title
    
    def test_generate_tool_title_long_pattern_truncated(self, task_tool):
        """Test that long patterns are truncated in title."""
        from wukong.core.session.models import ToolCallState, ToolStatus
        
        state = ToolCallState(
            tool_call_id="tc_001",
            tool_name="grep",
            arguments={"pattern": "a" * 50},  # Very long pattern
            status=ToolStatus.DONE,
        )
        
        title = task_tool._generate_tool_title(state)
        assert len(title) < 50  # Should be truncated
        assert "..." in title
    
    def test_create_filtered_registry_excludes_task(self, task_tool):
        """Test that task tool is excluded from filtered registry."""
        from wukong.core.tools.registry import ToolRegistry
        
        source_registry = ToolRegistry()
        source_registry.register_defaults()
        
        filtered = task_tool._create_filtered_registry(
            ["read_file", "task", "grep"],  # Include 'task' in list
            source_registry,
        )
        
        # Task should be excluded even if in the list
        assert "task" not in filtered
        assert "read_file" in filtered
        assert "grep" in filtered
    
    def test_format_output(self, task_tool):
        """Test output formatting."""
        metadata = TaskMetadata(
            session_id="ses_child",
            summary=[
                ToolCallSummary(
                    id="tc_001",
                    tool="read_file",
                    status="completed",
                    title="Read config.py",
                ),
            ],
        )
        
        output = task_tool._format_output(
            title="Test task",
            metadata=metadata,
            final_output="Task completed successfully.",
        )
        
        assert "<task_metadata>" in output
        assert "</task_metadata>" in output
        assert "ses_child" in output
        assert "Task completed successfully." in output


class TestDefaultAgents:
    """Tests for built-in default agent configurations."""
    
    def test_general_agent_defaults(self):
        """Test default general agent configuration."""
        assert "general" in DEFAULT_AGENTS
        config = AgentConfig.model_validate(DEFAULT_AGENTS["general"])
        
        assert config.name == "general"
        assert config.is_subagent()
        assert "read_file" in config.tools
        assert "write_file" in config.tools
        assert "bash" in config.tools
        assert "batch" in config.tools
        assert config.max_steps == 15
    
    def test_explore_agent_defaults(self):
        """Test default explore agent configuration."""
        assert "explore" in DEFAULT_AGENTS
        config = AgentConfig.model_validate(DEFAULT_AGENTS["explore"])
        
        assert config.name == "explore"
        assert config.is_subagent()
        assert "read_file" in config.tools
        assert "grep" in config.tools
        assert "batch" in config.tools
        # Explore should be read-only
        assert "write_file" not in config.tools
        assert "bash" not in config.tools
        assert config.max_steps == 10


class TestNestingDepth:
    """Tests for subagent nesting depth protection."""
    
    @pytest.fixture
    def task_tool(self):
        return TaskTool()
    
    def test_depth_zero_for_top_level(self, task_tool):
        """Top-level session (no parent) has depth 0."""
        session = MagicMock()
        session.parent_session_id = None
        manager = MagicMock()
        
        depth = task_tool._get_nesting_depth(session, manager)
        assert depth == 0
    
    def test_depth_one_for_child(self, task_tool):
        """Child session has depth 1."""
        parent = MagicMock()
        parent.parent_session_id = None
        
        child = MagicMock()
        child.parent_session_id = "parent_id"
        
        manager = MagicMock()
        manager.get_session.return_value = parent
        
        depth = task_tool._get_nesting_depth(child, manager)
        assert depth == 1
    
    def test_depth_two_for_grandchild(self, task_tool):
        """Grandchild session has depth 2."""
        grandparent = MagicMock()
        grandparent.parent_session_id = None
        
        parent = MagicMock()
        parent.parent_session_id = "grandparent_id"
        
        child = MagicMock()
        child.parent_session_id = "parent_id"
        
        manager = MagicMock()
        manager.get_session.side_effect = lambda sid: {
            "parent_id": parent,
            "grandparent_id": grandparent,
        }.get(sid)
        
        depth = task_tool._get_nesting_depth(child, manager)
        assert depth == 2
    
    @pytest.mark.asyncio
    async def test_nesting_depth_limit_rejects(self, task_tool):
        """Task is rejected when nesting depth exceeds MAX_NESTING_DEPTH."""
        # Build a chain of sessions deeper than MAX_NESTING_DEPTH
        sessions = {}
        prev_id = None
        for i in range(task_tool.MAX_NESTING_DEPTH + 1):
            sid = f"ses_{i}"
            s = MagicMock()
            s.session_id = sid
            s.parent_session_id = prev_id
            sessions[sid] = s
            prev_id = sid
        
        deepest_session = sessions[f"ses_{task_tool.MAX_NESTING_DEPTH}"]
        
        manager = MagicMock()
        manager.get_session.side_effect = lambda sid: sessions.get(sid)
        
        result = await task_tool.execute(
            workspace_dir="/tmp",
            agent="explore",
            prompt="test",
            session_manager=manager,
            parent_session=deepest_session,
            llm=MagicMock(),
        )
        
        assert result.success is False
        assert "nesting depth" in result.error.lower()


class TestCreateChildLLM:
    """Tests for LLM cloning with overrides."""
    
    @pytest.fixture
    def task_tool(self):
        return TaskTool()
    
    def test_no_overrides_returns_same_instance(self, task_tool):
        """When no overrides, return the original LLM."""
        llm = MagicMock()
        llm.model = "gpt-4"
        llm.temperature = 0.7
        
        result = task_tool._create_child_llm(llm)
        assert result is llm
    
    def test_model_override(self, task_tool):
        """Model override creates a copy with different model."""
        llm = MagicMock()
        llm.model = "gpt-4"
        llm.temperature = 0.7
        
        child = task_tool._create_child_llm(llm, model_override="gpt-3.5-turbo")
        
        assert child is not llm
        assert child.model == "gpt-3.5-turbo"
        assert llm.model == "gpt-4"  # Original unchanged
    
    def test_temperature_override(self, task_tool):
        """Temperature override creates a copy with different temperature."""
        llm = MagicMock()
        llm.model = "gpt-4"
        llm.temperature = 0.7
        
        child = task_tool._create_child_llm(llm, temperature_override=0.0)
        
        assert child is not llm
        assert child.temperature == 0.0
        assert llm.temperature == 0.7  # Original unchanged
    
    def test_both_overrides(self, task_tool):
        """Both model and temperature can be overridden simultaneously."""
        llm = MagicMock()
        llm.model = "gpt-4"
        llm.temperature = 0.7
        
        child = task_tool._create_child_llm(
            llm, model_override="claude-3", temperature_override=0.2
        )
        
        assert child.model == "claude-3"
        assert child.temperature == 0.2
        assert llm.model == "gpt-4"
        assert llm.temperature == 0.7


class TestReportProgress:
    """Tests for progress reporting."""
    
    @pytest.fixture
    def task_tool(self):
        return TaskTool()
    
    def test_tool_call_reported(self, task_tool):
        """Tool call events are reported to on_progress callback."""
        events = []
        callback = lambda e: events.append(e)
        
        chunk = MagicMock()
        chunk.content = None
        tc = MagicMock()
        tc.function.name = "grep"
        chunk.tool_calls = [tc]
        
        task_tool._report_progress(callback, "explore", "Find files", chunk)
        
        assert len(events) == 1
        assert events[0]["type"] == "tool_call"
        assert events[0]["agent"] == "explore"
        assert events[0]["tool"] == "grep"
    
    def test_text_content_reported(self, task_tool):
        """Text content events are reported."""
        events = []
        callback = lambda e: events.append(e)
        
        chunk = MagicMock()
        chunk.content = "Found 3 files matching the pattern."
        chunk.tool_calls = None
        
        task_tool._report_progress(callback, "explore", "Find files", chunk)
        
        assert len(events) == 1
        assert events[0]["type"] == "text"
        assert "Found 3 files" in events[0]["content"]
    
    def test_tool_result_header_emits_tool_done(self, task_tool):
        """Child agent tool result headers ([Tool:...]) emit a tool_done event."""
        events = []
        callback = lambda e: events.append(e)
        
        chunk = MagicMock()
        chunk.content = "[Tool: grep|1|0.5|{}]\nresult content"
        chunk.tool_calls = None
        
        task_tool._report_progress(callback, "explore", "Find files", chunk)
        
        assert len(events) == 1
        assert events[0]["type"] == "tool_done"
        assert events[0]["tool"] == "grep"
        assert events[0]["success"] is True
        assert events[0]["duration"] == 0.5
    
    def test_no_callback_no_error(self, task_tool):
        """Works without a callback (just logging)."""
        chunk = MagicMock()
        chunk.content = "some text"
        chunk.tool_calls = None
        
        # Should not raise
        task_tool._report_progress(None, "explore", "Find files", chunk)
    
    def test_callback_error_caught(self, task_tool):
        """Errors in the callback are caught and don't crash the task."""
        def bad_callback(e):
            raise RuntimeError("display error")
        
        chunk = MagicMock()
        chunk.content = "some text"
        chunk.tool_calls = None
        
        # Should not raise
        task_tool._report_progress(bad_callback, "explore", "Find files", chunk)


class TestReportToolDone:
    """Tests for _report_tool_done and _parse_batch_sub_items."""
    
    @pytest.fixture
    def task_tool(self):
        return TaskTool()
    
    def test_tool_done_event_structure(self, task_tool):
        """tool_done event has correct fields for a regular tool."""
        events = []
        callback = lambda e: events.append(e)
        
        task_tool._report_tool_done(
            callback, "explore", "Find files",
            "[Tool: read_file|1|0.3|{\"path\": \"a.py\"}]\nfile content",
        )
        
        assert len(events) == 1
        ev = events[0]
        assert ev["type"] == "tool_done"
        assert ev["tool"] == "read_file"
        assert ev["success"] is True
        assert ev["duration"] == pytest.approx(0.3, abs=0.01)
        assert ev["args"] == {"path": "a.py"}
        assert "batch_items" not in ev
    
    def test_batch_tool_done_includes_sub_items(self, task_tool):
        """tool_done for batch includes batch_items list."""
        events = []
        callback = lambda e: events.append(e)
        
        args_json = '{"tool_calls": [{"name": "grep", "arguments": {"pattern": "x"}}, {"name": "glob", "arguments": {"pattern": "*.py"}}]}'
        result = "Batch execution completed: 2/2 succeeded\n\n  [OK] grep\n  [OK] glob\n"
        content = f"[Tool: batch|1|1.5|{args_json}]\n{result}"
        
        task_tool._report_tool_done(callback, "explore", "T", content)
        
        assert len(events) == 1
        ev = events[0]
        assert ev["type"] == "tool_done"
        assert ev["tool"] == "batch"
        assert len(ev["batch_items"]) == 2
        assert ev["batch_items"][0]["name"] == "grep"
        assert ev["batch_items"][0]["success"] is True
        assert ev["batch_items"][1]["name"] == "glob"
    
    def test_batch_sub_item_failure(self, task_tool):
        """Batch sub-item marked as failed when result shows [FAIL]."""
        items = TaskTool._parse_batch_sub_items(
            {"tool_calls": [
                {"name": "grep", "arguments": {}},
                {"name": "read_file", "arguments": {"path": "missing.py"}},
            ]},
            "  [OK] grep\n  [FAIL] read_file\n    Error: File not found\n",
        )
        
        assert len(items) == 2
        assert items[0]["success"] is True
        assert items[1]["success"] is False
    
    def test_no_callback_skipped(self, task_tool):
        """No event emitted when callback is None."""
        task_tool._report_tool_done(
            None, "explore", "T",
            "[Tool: grep|1|0.5|{}]\nresult",
        )
    
    def test_malformed_header_skipped(self, task_tool):
        """Malformed [Tool:...] content is silently skipped."""
        events = []
        task_tool._report_tool_done(
            lambda e: events.append(e),
            "explore", "T",
            "[Tool: malformed content",
        )
        assert len(events) == 0


class TestContextKeys:
    """Tests for Tool context_keys declaration."""
    
    def test_task_tool_context_keys(self):
        """TaskTool declares correct context_keys."""
        tool = TaskTool()
        assert "session_manager" in tool.context_keys
        assert "parent_session" in tool.context_keys
        assert "llm" in tool.context_keys
        assert "tool_registry" in tool.context_keys
        assert "on_progress" in tool.context_keys
    
    def test_batch_tool_context_keys(self):
        """BatchTool declares correct context_keys."""
        from wukong.core.tools.builtins.batch import BatchTool
        tool = BatchTool()
        assert "tool_registry" in tool.context_keys
    
    def test_base_tool_context_keys_empty(self):
        """Base Tool has empty context_keys by default."""
        from wukong.core.tools.base import Tool, ToolResult
        
        class SimpleTool(Tool):
            name = "simple"
            description = "test"
            async def execute(self, **kwargs):
                return ToolResult.ok("ok")
        
        tool = SimpleTool()
        assert tool.context_keys == []


class TestBuildToolContext:
    """Tests for AgentLoop._build_tool_context."""
    
    def test_injects_declared_keys(self):
        """Tools receive only their declared context_keys."""
        from wukong.core.agent.loop import AgentLoop
        from wukong.core.session.models import Session
        
        mock_llm = MagicMock()
        mock_session = MagicMock(spec=Session)
        mock_session.workspace_directory = "/tmp"
        mock_session.mode = None
        mock_manager = MagicMock()
        
        loop = AgentLoop(
            llm=mock_llm,
            session=mock_session,
            session_manager=mock_manager,
        )
        
        tool = MagicMock()
        tool.context_keys = ["tool_registry", "llm"]
        
        ctx = loop._build_tool_context(tool)
        
        assert "tool_registry" in ctx
        assert "llm" in ctx
        assert ctx["llm"] is mock_llm
        assert "session_manager" not in ctx
        assert "parent_session" not in ctx
    
    def test_empty_context_keys(self):
        """Tool with no context_keys gets empty dict."""
        from wukong.core.agent.loop import AgentLoop
        from wukong.core.session.models import Session
        
        mock_session = MagicMock(spec=Session)
        mock_session.workspace_directory = "/tmp"
        mock_session.mode = None
        
        loop = AgentLoop(
            llm=MagicMock(),
            session=mock_session,
            session_manager=MagicMock(),
        )
        
        tool = MagicMock()
        tool.context_keys = []
        
        ctx = loop._build_tool_context(tool)
        assert ctx == {}
    
    def test_no_context_keys_attr(self):
        """Tool without context_keys attribute gets empty dict."""
        from wukong.core.agent.loop import AgentLoop
        from wukong.core.session.models import Session
        
        mock_session = MagicMock(spec=Session)
        mock_session.workspace_directory = "/tmp"
        mock_session.mode = None
        
        loop = AgentLoop(
            llm=MagicMock(),
            session=mock_session,
            session_manager=MagicMock(),
        )
        
        tool = MagicMock(spec=[])  # No attributes at all
        
        ctx = loop._build_tool_context(tool)
        assert ctx == {}


class TestTaskProgressHandler:
    """Tests for the CLI TaskProgressHandler."""
    
    def test_first_event_shows_header(self):
        """First tool_call event for a task triggers header display."""
        from wukong.cli import TaskProgressHandler
        
        handler = TaskProgressHandler()
        
        handler({"type": "tool_call", "agent": "explore", "task": "Find code", "tool": "grep"})
        
        assert handler.was_displayed("explore", "Find code")
    
    def test_subsequent_events_no_duplicate_header(self):
        """Multiple events for the same task don't create multiple headers."""
        from wukong.cli import TaskProgressHandler
        
        handler = TaskProgressHandler()
        
        handler({"type": "tool_call", "agent": "explore", "task": "Find code", "tool": "grep"})
        handler({"type": "tool_call", "agent": "explore", "task": "Find code", "tool": "read_file"})
        
        assert handler.was_displayed("explore", "Find code")
    
    def test_was_displayed_false_for_unknown(self):
        """was_displayed returns False for tasks that weren't shown."""
        from wukong.cli import TaskProgressHandler
        
        handler = TaskProgressHandler()
        assert handler.was_displayed("explore", "Find code") is False
    
    def test_reset_clears_state(self):
        """Reset clears all tracked state."""
        from wukong.cli import TaskProgressHandler
        
        handler = TaskProgressHandler()
        handler({"type": "tool_call", "agent": "explore", "task": "Find code", "tool": "grep"})
        
        handler.reset()
        assert handler.was_displayed("explore", "Find code") is False
    
    def test_thinking_start_stop_idempotent(self):
        """stop_thinking is safe to call multiple times."""
        from wukong.cli import TaskProgressHandler
        
        handler = TaskProgressHandler()
        # Should not raise even without calling start_thinking
        handler.stop_thinking()
        handler.stop_thinking()
    
    def test_tool_done_updates_done_count(self):
        """tool_done events increment the done counter."""
        from wukong.cli import TaskProgressHandler
        
        handler = TaskProgressHandler()
        handler({"type": "tool_call", "agent": "explore", "task": "T", "tool": "grep", "args": {}})
        assert handler._done_count == 0
        
        handler({"type": "tool_done", "agent": "explore", "task": "T", "tool": "grep", "success": True})
        assert handler._done_count == 1
    
    def test_tool_done_ignores_extra_events(self):
        """tool_done beyond the pending items count is safely ignored."""
        from wukong.cli import TaskProgressHandler
        
        handler = TaskProgressHandler()
        # No tool_call was registered, so tool_done should be a no-op
        handler({"type": "tool_done", "agent": "explore", "task": "T", "tool": "grep", "success": True})
        assert handler._done_count == 0
    
    def test_batch_sub_items_increase_line_count(self):
        """Batch tool_done with sub-items increases the line counter."""
        from wukong.cli import TaskProgressHandler
        
        handler = TaskProgressHandler()
        handler({"type": "tool_call", "agent": "explore", "task": "T", "tool": "batch", "args": {}})
        lines_before = handler._line_count
        
        handler({
            "type": "tool_done",
            "agent": "explore",
            "task": "T",
            "tool": "batch",
            "success": True,
            "batch_items": [
                {"name": "grep", "args": {"pattern": "foo"}, "success": True},
                {"name": "read_file", "args": {"path": "a.py"}, "success": True},
            ],
        })
        assert handler._line_count == lines_before + 2
    
    def test_reset_clears_line_tracking(self):
        """Reset also clears line tracking state."""
        from wukong.cli import TaskProgressHandler
        
        handler = TaskProgressHandler()
        handler({"type": "tool_call", "agent": "e", "task": "T", "tool": "grep"})
        handler.reset()
        
        assert handler._line_count == 0
        assert handler._tool_items == []
        assert handler._done_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
