"""
Tests for BatchTool.

Run with: pytest tests/test_batch_tool.py -v
"""

import tempfile
from pathlib import Path

import pytest

from wukong.core.tools.builtins.batch import BatchTool
from wukong.core.tools.registry import ToolRegistry


@pytest.fixture
def batch_tool():
    """Create a BatchTool instance."""
    return BatchTool()


@pytest.fixture
def tool_registry():
    """Create a ToolRegistry with default tools."""
    registry = ToolRegistry()
    registry.register_defaults()
    return registry


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some test files
        (Path(tmpdir) / "file1.txt").write_text("content of file 1")
        (Path(tmpdir) / "file2.txt").write_text("content of file 2")
        (Path(tmpdir) / "file3.txt").write_text("content of file 3")
        yield tmpdir


class TestBatchToolBasic:
    """Basic functionality tests for BatchTool."""
    
    @pytest.mark.asyncio
    async def test_parallel_read_files(self, batch_tool, tool_registry, temp_workspace):
        """Test parallel execution of multiple read_file calls."""
        result = await batch_tool.execute(
            workspace_dir=temp_workspace,
            tool_registry=tool_registry,
            tool_calls=[
                {"name": "read_file", "arguments": {"path": "file1.txt"}},
                {"name": "read_file", "arguments": {"path": "file2.txt"}},
                {"name": "read_file", "arguments": {"path": "file3.txt"}},
            ],
        )
        
        assert result.success is True
        assert "3/3 succeeded" in result.output
        assert result.metadata["success_count"] == 3
        assert result.metadata["failure_count"] == 0
    
    @pytest.mark.asyncio
    async def test_single_tool_call(self, batch_tool, tool_registry, temp_workspace):
        """Test batch with a single tool call."""
        result = await batch_tool.execute(
            workspace_dir=temp_workspace,
            tool_registry=tool_registry,
            tool_calls=[
                {"name": "list_dir", "arguments": {"path": "."}},
            ],
        )
        
        assert result.success is True
        assert "1/1 succeeded" in result.output
    
    @pytest.mark.asyncio
    async def test_mixed_tools(self, batch_tool, tool_registry, temp_workspace):
        """Test batch with different tool types."""
        result = await batch_tool.execute(
            workspace_dir=temp_workspace,
            tool_registry=tool_registry,
            tool_calls=[
                {"name": "read_file", "arguments": {"path": "file1.txt"}},
                {"name": "list_dir", "arguments": {"path": "."}},
                {"name": "glob", "arguments": {"pattern": "*.txt"}},
            ],
        )
        
        assert result.success is True
        assert "3/3 succeeded" in result.output


class TestBatchToolErrorHandling:
    """Error handling tests for BatchTool."""
    
    @pytest.mark.asyncio
    async def test_error_isolation(self, batch_tool, tool_registry, temp_workspace):
        """Test that one failure doesn't affect other tools."""
        result = await batch_tool.execute(
            workspace_dir=temp_workspace,
            tool_registry=tool_registry,
            tool_calls=[
                {"name": "read_file", "arguments": {"path": "file1.txt"}},
                {"name": "read_file", "arguments": {"path": "nonexistent.txt"}},  # Will fail
                {"name": "read_file", "arguments": {"path": "file2.txt"}},
            ],
        )
        
        assert result.success is True  # Batch itself succeeds
        assert result.metadata["success_count"] == 2
        assert result.metadata["failure_count"] == 1
        assert "[OK] read_file" in result.output
        assert "[FAIL] read_file" in result.output
    
    @pytest.mark.asyncio
    async def test_all_failures(self, batch_tool, tool_registry, temp_workspace):
        """Test batch where all tools fail."""
        result = await batch_tool.execute(
            workspace_dir=temp_workspace,
            tool_registry=tool_registry,
            tool_calls=[
                {"name": "read_file", "arguments": {"path": "nonexistent1.txt"}},
                {"name": "read_file", "arguments": {"path": "nonexistent2.txt"}},
            ],
        )
        
        assert result.success is True  # Batch itself still succeeds
        assert result.metadata["success_count"] == 0
        assert result.metadata["failure_count"] == 2
        assert "0/2 succeeded" in result.output


class TestBatchToolValidation:
    """Parameter validation tests for BatchTool."""
    
    @pytest.mark.asyncio
    async def test_missing_registry(self, batch_tool, temp_workspace):
        """Test batch without tool_registry."""
        result = await batch_tool.execute(
            workspace_dir=temp_workspace,
            # tool_registry is missing
            tool_calls=[
                {"name": "read_file", "arguments": {"path": "file1.txt"}},
            ],
        )
        
        assert result.success is False
        assert "tool_registry is required" in result.error
    
    @pytest.mark.asyncio
    async def test_empty_tool_calls(self, batch_tool, tool_registry, temp_workspace):
        """Test batch with empty tool_calls array."""
        result = await batch_tool.execute(
            workspace_dir=temp_workspace,
            tool_registry=tool_registry,
            tool_calls=[],
        )
        
        assert result.success is False
        assert "empty" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_unknown_tool(self, batch_tool, tool_registry, temp_workspace):
        """Test batch with unknown tool name."""
        result = await batch_tool.execute(
            workspace_dir=temp_workspace,
            tool_registry=tool_registry,
            tool_calls=[
                {"name": "unknown_tool", "arguments": {}},
            ],
        )
        
        assert result.success is False
        assert "unknown_tool" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_recursive_batch_blocked(self, batch_tool, tool_registry, temp_workspace):
        """Test that recursive batch calls are blocked."""
        result = await batch_tool.execute(
            workspace_dir=temp_workspace,
            tool_registry=tool_registry,
            tool_calls=[
                {"name": "batch", "arguments": {"tool_calls": []}},  # Nested batch
            ],
        )
        
        assert result.success is False
        assert "recursion" in result.error.lower() or "cannot be called" in result.error.lower()


class TestBatchToolMetadata:
    """Metadata and result format tests."""
    
    @pytest.mark.asyncio
    async def test_results_in_metadata(self, batch_tool, tool_registry, temp_workspace):
        """Test that detailed results are in metadata."""
        result = await batch_tool.execute(
            workspace_dir=temp_workspace,
            tool_registry=tool_registry,
            tool_calls=[
                {"name": "read_file", "arguments": {"path": "file1.txt"}},
                {"name": "read_file", "arguments": {"path": "file2.txt"}},
            ],
        )
        
        assert result.success is True
        assert "results" in result.metadata
        assert len(result.metadata["results"]) == 2
        
        # Check result structure
        for r in result.metadata["results"]:
            assert "index" in r
            assert "name" in r
            assert "success" in r
    
    @pytest.mark.asyncio
    async def test_results_ordered_by_index(self, batch_tool, tool_registry, temp_workspace):
        """Test that results maintain original order."""
        result = await batch_tool.execute(
            workspace_dir=temp_workspace,
            tool_registry=tool_registry,
            tool_calls=[
                {"name": "read_file", "arguments": {"path": "file1.txt"}},
                {"name": "read_file", "arguments": {"path": "file2.txt"}},
                {"name": "read_file", "arguments": {"path": "file3.txt"}},
            ],
        )
        
        results = result.metadata["results"]
        for i, r in enumerate(results):
            assert r["index"] == i


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
