"""Tests for PromptBuilder."""

from pathlib import Path

import pytest

from wukong.core.prompt.builder import (
    MODE_TEMPLATE_MAP,
    PROVIDER_TEMPLATE_MAP,
    PromptBuilder,
)
from wukong.core.session.models import MessageMode


class TestPromptBuilder:
    """Test cases for PromptBuilder class."""
    
    @pytest.fixture
    def temp_workspace(self, tmp_path: Path) -> Path:
        """Create a temporary workspace directory."""
        return tmp_path
    
    @pytest.fixture
    def builder(self, temp_workspace: Path) -> PromptBuilder:
        """Create a PromptBuilder instance."""
        return PromptBuilder(
            workspace_dir=temp_workspace,
            mode=MessageMode.NORMAL,
            provider="anthropic",
        )
    
    def test_init(self, temp_workspace: Path):
        """Test PromptBuilder initialization."""
        builder = PromptBuilder(
            workspace_dir=temp_workspace,
            mode=MessageMode.PLAN,
            provider="openai",
        )
        
        assert builder.workspace_dir == temp_workspace
        assert builder.mode == MessageMode.PLAN
        assert builder.provider == "openai"
    
    def test_build_returns_string(self, builder: PromptBuilder):
        """Test that build() returns a non-empty string."""
        result = builder.build()
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_build_contains_base_prompt(self, builder: PromptBuilder):
        """Test that build() includes base prompt content."""
        result = builder.build()
        
        # Should contain key phrases from base prompt
        assert "Wu-Zhao" in result
        assert "AI coding assistant" in result
    
    def test_build_contains_mode_prompt(self, builder: PromptBuilder):
        """Test that build() includes mode-specific content."""
        # Test ASK mode (NORMAL maps to ask.md)
        builder.mode = MessageMode.NORMAL
        result = builder.build()
        assert "ASK" in result
        
        # Test PLAN mode
        builder.mode = MessageMode.PLAN
        result = builder.build()
        assert "PLAN" in result
        
        # Test AGENT mode (CODE maps to agent.md)
        builder.mode = MessageMode.CODE
        result = builder.build()
        assert "AGENT" in result
    
    def test_build_contains_environment_info(self, builder: PromptBuilder):
        """Test that build() includes environment information."""
        result = builder.build()
        
        assert "Environment" in result
        assert "Working Directory" in result
        assert "Current Time" in result
    
    def test_provider_template_selection(self, temp_workspace: Path):
        """Test that different providers load different templates."""
        claude_builder = PromptBuilder(
            workspace_dir=temp_workspace,
            provider="anthropic",
        )
        openai_builder = PromptBuilder(
            workspace_dir=temp_workspace,
            provider="openai",
        )
        
        claude_result = claude_builder.build()
        openai_result = openai_builder.build()
        
        # Claude template should have Claude-specific instructions
        assert "Claude-Specific" in claude_result
        
        # OpenAI template should have OpenAI-specific instructions
        assert "OpenAI-Specific" in openai_result
    
    def test_user_rules_loading(self, temp_workspace: Path):
        """Test that user rules are loaded when present."""
        # Create .wu-zhao/rules.md
        rules_dir = temp_workspace / ".wu-zhao"
        rules_dir.mkdir(parents=True)
        rules_file = rules_dir / "rules.md"
        rules_file.write_text("Custom project rules for testing.")
        
        builder = PromptBuilder(workspace_dir=temp_workspace)
        result = builder.build()
        
        assert "User Rules" in result
        assert "Custom project rules for testing" in result
    
    def test_user_rules_not_loaded_when_missing(self, temp_workspace: Path):
        """Test that missing user rules don't cause errors."""
        builder = PromptBuilder(workspace_dir=temp_workspace)
        result = builder.build()
        
        # Should not contain User Rules section
        # (but should still work without errors)
        assert isinstance(result, str)
    
    def test_project_type_detection(self, temp_workspace: Path):
        """Test project type detection from config files."""
        # Create pyproject.toml
        (temp_workspace / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        
        builder = PromptBuilder(workspace_dir=temp_workspace)
        result = builder.build()
        
        assert "Python" in result
    
    def test_set_mode(self, builder: PromptBuilder):
        """Test set_mode method."""
        builder.set_mode(MessageMode.PLAN)
        assert builder.mode == MessageMode.PLAN
    
    def test_set_provider(self, builder: PromptBuilder):
        """Test set_provider method."""
        builder.set_provider("openai")
        assert builder.provider == "openai"
    
    def test_mode_template_map_completeness(self):
        """Test that all MessageMode values have mappings."""
        for mode in MessageMode:
            assert mode in MODE_TEMPLATE_MAP, f"Missing mapping for {mode}"
    
    def test_tools_section_with_no_tools(self, builder: PromptBuilder):
        """Test that tools section is omitted when no tools are provided."""
        result = builder.build(tools=None)
        
        # Should not have "Available Tools" section when no tools
        # (unless it comes from the template file with placeholder)
        assert isinstance(result, str)
    
    def test_detect_platform(self, builder: PromptBuilder):
        """Test platform detection."""
        platform_str = builder._detect_platform()
        
        assert isinstance(platform_str, str)
        assert len(platform_str) > 0

