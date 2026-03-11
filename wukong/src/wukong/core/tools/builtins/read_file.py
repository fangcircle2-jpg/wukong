"""Read file tool."""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from wukong.core.tools.base import Tool, ToolResult, ToolError


def _load_description() -> str:
    """Load tool description from text file."""
    desc_file = Path(__file__).parent / "read_file.txt"
    if desc_file.exists():
        return desc_file.read_text(encoding="utf-8").strip()
    return "Read the contents of a file."


class ReadFileParams(BaseModel):
    """Parameters for read_file tool."""
    path: str = Field(description="Path to the file to read (relative to workspace)")
    offset: int | None = Field(default=None, description="Line number to start reading from (1-based)")
    limit: int | None = Field(default=None, description="Maximum number of lines to read")


class ReadFileTool(Tool):
    """Tool to read file contents."""
    
    name = "read_file"
    description = _load_description()
    parameters = ReadFileParams
    
    async def execute(
        self,
        *,
        workspace_dir: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        """Read file contents.
        
        Args:
            workspace_dir: Workspace directory path.
            **kwargs: Tool parameters (path, offset, limit).
            
        Returns:
            ToolResult with file content or error.
        """
        # Validate parameters
        try:
            params = self.validate_params(**kwargs)
        except Exception as e:
            return ToolResult.fail(f"Invalid parameters: {e}")
        
        # Resolve file path
        file_path = params.path
        if workspace_dir and not os.path.isabs(file_path):
            file_path = os.path.join(workspace_dir, file_path)
        
        # Check file exists
        if not os.path.exists(file_path):
            return ToolResult.fail(f"File not found: {params.path}")
        
        if not os.path.isfile(file_path):
            return ToolResult.fail(f"Not a file: {params.path}")
        
        # Read file
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            # Apply offset and limit
            total_lines = len(lines)
            start = 0
            end = total_lines
            
            if params.offset is not None:
                start = max(0, params.offset - 1)  # Convert to 0-based
            
            if params.limit is not None:
                end = min(total_lines, start + params.limit)
            
            selected_lines = lines[start:end]
            content = "".join(selected_lines)
            
            # Build metadata
            metadata = {
                "path": params.path,
                "total_lines": total_lines,
                "start_line": start + 1,
                "end_line": end,
            }
            
            return ToolResult.ok(content, **metadata)
            
        except UnicodeDecodeError:
            return ToolResult.fail(f"Cannot read file (not UTF-8 encoded): {params.path}")
        except PermissionError:
            return ToolResult.fail(f"Permission denied: {params.path}")
        except Exception as e:
            return ToolResult.fail(f"Failed to read file: {e}")
