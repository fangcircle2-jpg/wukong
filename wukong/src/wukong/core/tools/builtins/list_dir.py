"""List directory tool."""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from wukong.core.tools.base import Tool, ToolResult, ToolError


def _load_description() -> str:
    """Load tool description from text file."""
    desc_file = Path(__file__).parent / "list_dir.txt"
    if desc_file.exists():
        return desc_file.read_text(encoding="utf-8").strip()
    return "List the contents of a directory."


class ListDirParams(BaseModel):
    """Parameters for list_dir tool."""
    path: str = Field(default=".", description="Path to the directory to list (relative to workspace)")
    recursive: bool = Field(default=False, description="List contents recursively")
    max_depth: int = Field(default=3, description="Maximum depth for recursive listing")


class ListDirTool(Tool):
    """Tool to list directory contents."""
    
    name = "list_dir"
    description = _load_description()
    parameters = ListDirParams
    
    async def execute(
        self,
        *,
        workspace_dir: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        """List directory contents.
        
        Args:
            workspace_dir: Workspace directory path.
            **kwargs: Tool parameters (path, recursive, max_depth).
            
        Returns:
            ToolResult with directory listing or error.
        """
        # Validate parameters
        try:
            params = self.validate_params(**kwargs)
        except Exception as e:
            return ToolResult.fail(f"Invalid parameters: {e}")
        
        # Resolve directory path
        dir_path = params.path
        if workspace_dir and not os.path.isabs(dir_path):
            dir_path = os.path.join(workspace_dir, dir_path)
        
        # Check directory exists
        if not os.path.exists(dir_path):
            return ToolResult.fail(f"Directory not found: {params.path}")
        
        if not os.path.isdir(dir_path):
            return ToolResult.fail(f"Not a directory: {params.path}")
        
        # List directory
        try:
            if params.recursive:
                output = self._list_recursive(dir_path, params.max_depth)
            else:
                output = self._list_flat(dir_path)
            
            return ToolResult.ok(output, path=params.path)
            
        except PermissionError:
            return ToolResult.fail(f"Permission denied: {params.path}")
        except Exception as e:
            return ToolResult.fail(f"Failed to list directory: {e}")
    
    def _list_flat(self, dir_path: str) -> str:
        """List directory contents (flat)."""
        entries = []
        
        for name in sorted(os.listdir(dir_path)):
            full_path = os.path.join(dir_path, name)
            if os.path.isdir(full_path):
                entries.append(f"[DIR]  {name}/")
            else:
                entries.append(f"[FILE] {name}")
        
        if not entries:
            return "(empty directory)"
        
        return "\n".join(entries)
    
    def _list_recursive(self, dir_path: str, max_depth: int, current_depth: int = 0, prefix: str = "") -> str:
        """List directory contents recursively with tree structure."""
        if current_depth > max_depth:
            return ""
        
        lines = []
        
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return f"{prefix}(permission denied)"
        
        for i, name in enumerate(entries):
            is_last = (i == len(entries) - 1)
            full_path = os.path.join(dir_path, name)
            
            # Tree characters
            connector = "└── " if is_last else "├── "
            
            if os.path.isdir(full_path):
                lines.append(f"{prefix}{connector}{name}/")
                
                # Recurse into subdirectory
                if current_depth < max_depth:
                    extension = "    " if is_last else "│   "
                    sub_content = self._list_recursive(
                        full_path, 
                        max_depth, 
                        current_depth + 1,
                        prefix + extension
                    )
                    if sub_content:
                        lines.append(sub_content)
            else:
                lines.append(f"{prefix}{connector}{name}")
        
        return "\n".join(lines)
