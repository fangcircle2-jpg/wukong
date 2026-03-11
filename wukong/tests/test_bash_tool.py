"""
Tests for BashTool.

Run with: pytest tests/test_bash_tool.py -v
"""

import tempfile
from pathlib import Path

import pytest

from wukong.core.tools.builtins.bash import BashTool


@pytest.fixture
def bash_tool():
    """Create a BashTool instance."""
    return BashTool()


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestBashToolBasic:
    """Basic functionality tests for BashTool."""
    
    @pytest.mark.asyncio
    async def test_simple_command(self, bash_tool, temp_workspace):
        """Test executing a simple command."""
        result = await bash_tool.execute(
            workspace_dir=temp_workspace,
            command="echo hello",
        )
        
        assert result.success is True
        assert "hello" in result.output
    
    @pytest.mark.asyncio
    async def test_command_with_exit_code(self, bash_tool, temp_workspace):
        """Test command that fails with non-zero exit code."""
        # Use a command that will fail
        result = await bash_tool.execute(
            workspace_dir=temp_workspace,
            command="exit 1",
        )
        
        assert result.success is True  # Tool execution succeeded
        assert result.metadata.get("exit_code") == 1
        assert "[exit code: 1]" in result.output
    
    @pytest.mark.asyncio
    async def test_command_with_workdir(self, bash_tool, temp_workspace):
        """Test command with custom working directory."""
        # Create a subdirectory
        subdir = Path(temp_workspace) / "subdir"
        subdir.mkdir()
        
        # Run pwd in the subdirectory
        result = await bash_tool.execute(
            workspace_dir=temp_workspace,
            command="cd .",  # Just verify it runs in the right dir
            workdir="subdir",
        )
        
        assert result.success is True
        assert result.metadata.get("cwd").endswith("subdir")
    
    @pytest.mark.asyncio
    async def test_command_captures_stderr(self, bash_tool, temp_workspace):
        """Test that stderr is captured."""
        result = await bash_tool.execute(
            workspace_dir=temp_workspace,
            command="echo error >&2",
        )
        
        assert result.success is True
        assert "[stderr]" in result.output
        assert "error" in result.output
    
    @pytest.mark.asyncio
    async def test_nonexistent_workdir(self, bash_tool, temp_workspace):
        """Test with non-existent working directory."""
        result = await bash_tool.execute(
            workspace_dir=temp_workspace,
            command="echo test",
            workdir="nonexistent",
        )
        
        assert result.success is False
        assert "not found" in result.error.lower()


class TestBashToolTimeout:
    """Timeout related tests for BashTool."""
    
    @pytest.mark.asyncio
    async def test_command_timeout(self, bash_tool, temp_workspace):
        """Test command that times out."""
        import sys
        
        # Use platform-appropriate sleep command
        if sys.platform == "win32":
            # Windows: ping localhost with delay (each ping ~1 second)
            command = "ping -n 10 127.0.0.1"
        else:
            command = "sleep 10"
        
        result = await bash_tool.execute(
            workspace_dir=temp_workspace,
            command=command,
            timeout=100,  # 100ms = 0.1 seconds
        )
        
        assert result.success is False
        assert "timed out" in result.error.lower()
        assert "100ms" in result.error


class TestBashToolParameters:
    """Parameter validation tests."""
    
    @pytest.mark.asyncio
    async def test_missing_command(self, bash_tool, temp_workspace):
        """Test with missing command parameter."""
        result = await bash_tool.execute(
            workspace_dir=temp_workspace,
            # command is missing
        )
        
        assert result.success is False
        assert "invalid parameters" in result.error.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
