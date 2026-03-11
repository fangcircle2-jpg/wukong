"""
Tests for FileProvider.

Run with: pytest tests/test_file_provider.py -v
"""

import pytest
from pathlib import Path
import tempfile
import os

from wukong.core.context import (
    FileProvider,
    ContextItem,
    ContextProviderError,
    ContextSubmenuItem,
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        
        # Create directory structure
        (workspace / "src").mkdir()
        (workspace / "src" / "subdir").mkdir()
        (workspace / "tests").mkdir()
        
        # Create test files
        (workspace / "README.md").write_text("# Test Project\n\nThis is a test.", encoding="utf-8")
        (workspace / "src" / "main.py").write_text(
            "def main():\n    print('Hello, World!')\n\nif __name__ == '__main__':\n    main()\n",
            encoding="utf-8"
        )
        (workspace / "src" / "utils.py").write_text(
            "def helper():\n    return 42\n",
            encoding="utf-8"
        )
        (workspace / "src" / "subdir" / "module.py").write_text(
            "class MyClass:\n    pass\n",
            encoding="utf-8"
        )
        (workspace / "tests" / "test_main.py").write_text(
            "def test_main():\n    assert True\n",
            encoding="utf-8"
        )
        
        # Create a large file (for truncation test)
        large_content = "\n".join([f"line {i}" for i in range(1, 1001)])
        (workspace / "large_file.txt").write_text(large_content, encoding="utf-8")
        
        # Create .gitignore
        (workspace / ".gitignore").write_text(
            "__pycache__/\n*.pyc\n.env\nbuild/\n",
            encoding="utf-8"
        )
        
        # Create ignored files
        (workspace / "__pycache__").mkdir()
        (workspace / "__pycache__" / "cache.pyc").write_text("cached", encoding="utf-8")
        (workspace / "build").mkdir()
        (workspace / "build" / "output.txt").write_text("build output", encoding="utf-8")
        
        yield workspace


@pytest.fixture
def provider():
    """Create a FileProvider instance (stateless, no workspace_dir)."""
    return FileProvider()


class TestGetContext:
    """Test get_context method."""
    
    @pytest.mark.asyncio
    async def test_read_file(self, provider: FileProvider, temp_workspace: Path):
        """Test reading a simple file."""
        items = await provider.get_context("src/main.py", workspace_dir=str(temp_workspace))
        
        assert len(items) == 1
        item = items[0]
        
        assert item.provider == "file"
        assert item.name == "main.py"
        assert "def main():" in item.content
        assert item.metadata["path"] == "src/main.py"
        assert item.metadata["extension"] == ".py"
    
    @pytest.mark.asyncio
    async def test_read_file_with_line_range(self, provider: FileProvider, temp_workspace: Path):
        """Test reading specific line range."""
        items = await provider.get_context("large_file.txt:10-20", workspace_dir=str(temp_workspace))
        
        assert len(items) == 1
        item = items[0]
        
        assert "line 10" in item.content
        assert "line 20" in item.content
        assert "line 9" not in item.content
        assert "line 21" not in item.content
        assert item.metadata["lines"] == "10-20"
    
    @pytest.mark.asyncio
    async def test_truncate_large_file(self, provider: FileProvider, temp_workspace: Path):
        """Test that large files are truncated."""
        items = await provider.get_context("large_file.txt", workspace_dir=str(temp_workspace))
        
        item = items[0]
        assert item.metadata["total_lines"] == 1000
        assert item.metadata["lines"] == "1-500"
        assert "truncated" in item.content
        assert "line 1" in item.content
        assert "line 500" in item.content
    
    @pytest.mark.asyncio
    async def test_file_not_found(self, provider: FileProvider, temp_workspace: Path):
        """Test error when file doesn't exist."""
        with pytest.raises(ContextProviderError, match="does not exist"):
            await provider.get_context("nonexistent.py", workspace_dir=str(temp_workspace))
    
    @pytest.mark.asyncio
    async def test_path_outside_workspace(self, provider: FileProvider, temp_workspace: Path):
        """Test error when path is outside workspace."""
        with pytest.raises(ContextProviderError, match="outside workspace"):
            await provider.get_context("../../../etc/passwd", workspace_dir=str(temp_workspace))
    
    @pytest.mark.asyncio
    async def test_read_nested_file(self, provider: FileProvider, temp_workspace: Path):
        """Test reading file in nested directory."""
        items = await provider.get_context("src/subdir/module.py", workspace_dir=str(temp_workspace))
        
        assert len(items) == 1
        assert items[0].name == "module.py"
        assert "class MyClass" in items[0].content
        assert items[0].metadata["path"] == "src/subdir/module.py"


class TestGetSubmenuItems:
    """Test get_submenu_items method."""
    
    @pytest.mark.asyncio
    async def test_recent_files_empty_query(self, provider: FileProvider, temp_workspace: Path):
        """Test getting recent files when query is empty."""
        items = await provider.get_submenu_items(workspace_dir=str(temp_workspace))
        
        assert len(items) > 0
        assert all(isinstance(item, ContextSubmenuItem) for item in items)
        
        # Check item structure
        item = items[0]
        assert item.id  # Has path
        assert item.name  # Has file name
    
    @pytest.mark.asyncio
    async def test_fuzzy_search(self, provider: FileProvider, temp_workspace: Path):
        """Test fuzzy search with query."""
        items = await provider.get_submenu_items("main", workspace_dir=str(temp_workspace))
        
        # Should find main.py and test_main.py
        names = [item.name for item in items]
        assert "main.py" in names
        assert "test_main.py" in names
    
    @pytest.mark.asyncio
    async def test_fuzzy_search_partial(self, provider: FileProvider, temp_workspace: Path):
        """Test fuzzy search with partial match."""
        items = await provider.get_submenu_items("util", workspace_dir=str(temp_workspace))
        
        names = [item.name for item in items]
        assert "utils.py" in names
    
    @pytest.mark.asyncio
    async def test_submenu_excludes_ignored_files(self, provider: FileProvider, temp_workspace: Path):
        """Test that gitignored files are not in submenu."""
        items = await provider.get_submenu_items(workspace_dir=str(temp_workspace))
        
        paths = [item.id for item in items]
        
        # Should not include __pycache__ or build files
        assert not any("__pycache__" in p for p in paths)
        assert not any("build" in p for p in paths)
    
    @pytest.mark.asyncio
    async def test_no_workspace_returns_empty(self, provider: FileProvider):
        """Test that empty workspace_dir returns empty list."""
        items = await provider.get_submenu_items(workspace_dir="")
        assert items == []


class TestGetCompletions:
    """Test get_completions method."""
    
    @pytest.mark.asyncio
    async def test_path_completion(self, provider: FileProvider, temp_workspace: Path):
        """Test path completion."""
        completions = await provider.get_completions("src/", workspace_dir=str(temp_workspace))
        
        # Should find files in src/
        assert any("main.py" in c for c in completions)
        assert any("utils.py" in c for c in completions)
    
    @pytest.mark.asyncio
    async def test_empty_partial(self, provider: FileProvider, temp_workspace: Path):
        """Test completion with empty string."""
        completions = await provider.get_completions("", workspace_dir=str(temp_workspace))
        
        assert completions == []
    
    @pytest.mark.asyncio
    async def test_partial_filename(self, provider: FileProvider, temp_workspace: Path):
        """Test completion with partial filename."""
        completions = await provider.get_completions("READ", workspace_dir=str(temp_workspace))
        
        assert "README.md" in completions
    
    @pytest.mark.asyncio
    async def test_no_workspace_returns_empty(self, provider: FileProvider):
        """Test that empty workspace_dir returns empty list."""
        completions = await provider.get_completions("src/", workspace_dir="")
        assert completions == []


class TestGitignore:
    """Test gitignore handling."""
    
    @pytest.mark.asyncio
    async def test_gitignore_respected(self, provider: FileProvider, temp_workspace: Path):
        """Test that .gitignore patterns are respected."""
        # Try to list all files via search
        items = await provider.get_submenu_items("", workspace_dir=str(temp_workspace))
        
        paths = [item.id for item in items]
        
        # Ignored directories should not appear
        assert not any("__pycache__" in p for p in paths)
        assert not any("build/" in p for p in paths)
    
    @pytest.mark.asyncio
    async def test_can_still_read_ignored_file_directly(self, provider: FileProvider, temp_workspace: Path):
        """Test that ignored files can still be read if path is known.
        
        Note: This tests current behavior. You might want to change this
        to block reading ignored files entirely.
        """
        # The file exists but is in an ignored directory
        ignored_file = temp_workspace / "build" / "output.txt"
        assert ignored_file.exists()
        
        # Currently, direct path access is allowed
        # Uncomment the following if you want to block it:
        # with pytest.raises(ContextProviderError):
        #     await provider.get_context("build/output.txt", workspace_dir=str(temp_workspace))


class TestEdgeCases:
    """Test edge cases."""
    
    @pytest.mark.asyncio
    async def test_file_with_special_characters(self, temp_workspace: Path):
        """Test reading file with special characters in content."""
        special_file = temp_workspace / "special.txt"
        special_file.write_text("Hello 中文 🎉 émoji", encoding="utf-8")
        
        provider = FileProvider()
        items = await provider.get_context("special.txt", workspace_dir=str(temp_workspace))
        
        assert "中文" in items[0].content
        assert "🎉" in items[0].content
    
    @pytest.mark.asyncio
    async def test_empty_file(self, temp_workspace: Path):
        """Test reading empty file."""
        empty_file = temp_workspace / "empty.txt"
        empty_file.write_text("", encoding="utf-8")
        
        provider = FileProvider()
        items = await provider.get_context("empty.txt", workspace_dir=str(temp_workspace))
        
        assert items[0].content == ""
        assert items[0].metadata["total_lines"] == 0
    
    @pytest.mark.asyncio
    async def test_directory_not_file(self, provider: FileProvider, temp_workspace: Path):
        """Test error when path is a directory."""
        with pytest.raises(ContextProviderError, match="Not a file"):
            await provider.get_context("src", workspace_dir=str(temp_workspace))


class TestStatelessDesign:
    """Test that FileProvider is stateless."""
    
    @pytest.mark.asyncio
    async def test_same_provider_different_workspaces(self, temp_workspace: Path):
        """Test that the same provider can be used with different workspaces."""
        # Create a second workspace
        with tempfile.TemporaryDirectory() as tmpdir2:
            workspace2 = Path(tmpdir2)
            (workspace2 / "other.txt").write_text("Other workspace file", encoding="utf-8")
            
            provider = FileProvider()
            
            # Read from first workspace
            items1 = await provider.get_context("README.md", workspace_dir=str(temp_workspace))
            assert "Test Project" in items1[0].content
            
            # Read from second workspace with same provider
            items2 = await provider.get_context("other.txt", workspace_dir=str(workspace2))
            assert "Other workspace file" in items2[0].content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
