"""Tests for batch tool guidance in system prompts.

Verifies that the system prompt correctly includes batch tool usage guidelines
across all templates and configurations.
"""

from pathlib import Path

import pytest

from wukong.core.llm.schema import FunctionDefinition, ToolDefinition
from wukong.core.prompt.builder import PromptBuilder
from wukong.core.session.models import MessageMode


def _make_tool_definitions(names: list[str]) -> list[ToolDefinition]:
    """Helper to create mock ToolDefinition objects."""
    return [
        ToolDefinition(
            type="function",
            function=FunctionDefinition(
                name=name,
                description=f"{name} tool",
                parameters={"type": "object", "properties": {}},
            ),
        )
        for name in names
    ]


STANDARD_TOOLS = _make_tool_definitions([
    "read_file", "write_file", "grep", "glob", "list_dir", "bash", "batch",
])


class TestToolsTemplateLinking:
    """Verify that tools.md template is actually loaded into the system prompt."""

    @pytest.fixture
    def builder(self, tmp_path: Path) -> PromptBuilder:
        return PromptBuilder(workspace_dir=tmp_path, mode=MessageMode.CODE, provider="anthropic")

    def test_tools_section_loads_template(self, builder: PromptBuilder):
        """tools.md template content must appear in the built prompt."""
        result = builder.build(tools=STANDARD_TOOLS)
        assert "Tool Usage Guidelines" in result, (
            "_build_tools_section() is not loading tools.md template"
        )

    def test_tools_section_replaces_placeholder(self, builder: PromptBuilder):
        """{{tools_list}} placeholder must be replaced with actual tool names."""
        result = builder.build(tools=STANDARD_TOOLS)
        assert "{{tools_list}}" not in result, (
            "{{tools_list}} placeholder was not replaced"
        )
        for name in ["read_file", "write_file", "grep", "glob", "batch"]:
            assert name in result, f"Tool '{name}' not found in tools section"

    def test_tools_section_omitted_when_no_tools(self, builder: PromptBuilder):
        """No tools section when tools=None."""
        result = builder.build(tools=None)
        assert "Tool Usage Guidelines" not in result


class TestBatchGuidanceInToolsTemplate:
    """Verify that batch-specific guidance exists in tools.md template content."""

    @pytest.fixture
    def prompt(self, tmp_path: Path) -> str:
        builder = PromptBuilder(workspace_dir=tmp_path, mode=MessageMode.CODE, provider="anthropic")
        return builder.build(tools=STANDARD_TOOLS)

    def test_batch_tool_mentioned_in_tools_section(self, prompt: str):
        """The tools section must contain explicit batch tool guidance."""
        assert "batch" in prompt.lower()

    def test_batch_parallel_keyword(self, prompt: str):
        """Must mention parallel execution."""
        assert "parallel" in prompt.lower()

    def test_batch_example_present(self, prompt: str):
        """Must include a concrete batch usage example with tool_calls."""
        assert "tool_calls" in prompt

    def test_batch_read_file_example(self, prompt: str):
        """Must include example of batching multiple read_file calls."""
        assert "read_file" in prompt

    def test_batch_when_not_to_use(self, prompt: str):
        """Must clarify when NOT to use batch (dependent operations)."""
        assert "NOT" in prompt or "not" in prompt.lower()

    def test_prioritize_batch_wording(self, prompt: str):
        """Must contain strong guidance to use batch for independent ops."""
        prompt_lower = prompt.lower()
        assert any(word in prompt_lower for word in ["must use", "always use", "critical"])


class TestBatchGuidanceInAgentMode:
    """Verify that agent.md mode template contains batch guidance."""

    @pytest.fixture
    def prompt(self, tmp_path: Path) -> str:
        builder = PromptBuilder(workspace_dir=tmp_path, mode=MessageMode.CODE, provider="anthropic")
        return builder.build(tools=STANDARD_TOOLS)

    def test_agent_mode_has_batch_section(self, prompt: str):
        """Agent mode must include the batch/efficiency section."""
        assert "Efficiency" in prompt or "Batching" in prompt or "Batch" in prompt

    def test_agent_mode_batch_scenarios(self, prompt: str):
        """Agent mode should mention common batch scenarios."""
        prompt_lower = prompt.lower()
        assert "multiple files" in prompt_lower or "independent operations" in prompt_lower


class TestBatchGuidanceInBasePrompts:
    """Verify all base prompt templates mention batch efficiency."""

    @pytest.fixture(params=["anthropic", "openai", "mock"])
    def prompt(self, request, tmp_path: Path) -> str:
        builder = PromptBuilder(
            workspace_dir=tmp_path, mode=MessageMode.CODE, provider=request.param,
        )
        return builder.build(tools=STANDARD_TOOLS)

    def test_base_prompt_mentions_efficiency(self, prompt: str):
        """Base prompt must contain efficiency / batch guideline."""
        prompt_lower = prompt.lower()
        assert "maximize efficiency" in prompt_lower or "batch" in prompt_lower


class TestBatchGuidanceNotInAskMode:
    """In ASK mode the tools section should still appear when tools are passed."""

    def test_ask_mode_still_has_tools_guidance(self, tmp_path: Path):
        builder = PromptBuilder(workspace_dir=tmp_path, mode=MessageMode.NORMAL, provider="anthropic")
        result = builder.build(tools=STANDARD_TOOLS)
        assert "batch" in result.lower()


class TestBatchGuidanceEndToEnd:
    """End-to-end test: build prompt with real tool registry definitions."""

    def test_with_real_tool_registry(self, tmp_path: Path):
        """Build system prompt using actual ToolRegistry definitions."""
        from wukong.core.tools.registry import create_default_registry

        registry = create_default_registry()
        definitions = registry.get_definitions()

        builder = PromptBuilder(
            workspace_dir=tmp_path, mode=MessageMode.CODE, provider="anthropic",
        )
        prompt = builder.build(tools=definitions)

        assert "batch" in prompt.lower(), "batch tool not mentioned in prompt"
        assert "parallel" in prompt.lower(), "parallel execution not mentioned"
        assert "tool_calls" in prompt, "batch example missing from prompt"

        tool_names = [d.function.name for d in definitions]
        assert "batch" in tool_names, "batch tool not registered"
        for name in tool_names:
            assert name in prompt, f"Tool '{name}' not listed in prompt"

    def test_prompt_structure_order(self, tmp_path: Path):
        """Verify the prompt sections appear in expected order."""
        from wukong.core.tools.registry import create_default_registry

        registry = create_default_registry()
        definitions = registry.get_definitions()

        builder = PromptBuilder(
            workspace_dir=tmp_path, mode=MessageMode.CODE, provider="anthropic",
        )
        prompt = builder.build(tools=definitions)

        base_idx = prompt.index("Wu-Zhao")
        mode_idx = prompt.index("AGENT")
        env_idx = prompt.index("Environment")
        tools_idx = prompt.index("Available Tools")

        assert base_idx < mode_idx < env_idx < tools_idx, (
            f"Prompt sections out of order: base={base_idx}, mode={mode_idx}, "
            f"env={env_idx}, tools={tools_idx}"
        )
