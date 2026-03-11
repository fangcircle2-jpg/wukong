"""Write file tool."""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from wukong.core.tools.base import Tool, ToolResult, ToolError


def _load_description() -> str:
    """Load tool description from text file."""
    desc_file = Path(__file__).parent / "write_file.txt"
    if desc_file.exists():
        return desc_file.read_text(encoding="utf-8").strip()
    return "Write content to a file."


class WriteFileParams(BaseModel):
    """Parameters for write_file tool."""
    path: str = Field(description="Path to the file to write (relative to workspace)")
    content: str = Field(description="Content to write to the file")
    create_dirs: bool = Field(default=True, description="Create parent directories if they don't exist")


class WriteFileTool(Tool):
    """Tool to write file contents."""
    
    name = "write_file"
    description = _load_description()
    parameters = WriteFileParams
    
    async def execute(
        self,
        *,
        workspace_dir: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        """Write content to file.
        
        Args:
            workspace_dir: Workspace directory path.
            **kwargs: Tool parameters (path, content, create_dirs).
            
        Returns:
            ToolResult with success message or error.
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
        
        # Create parent directories if needed
        parent_dir = os.path.dirname(file_path)
        if parent_dir and params.create_dirs:
            try:
                os.makedirs(parent_dir, exist_ok=True)
            except Exception as e:
                return ToolResult.fail(f"Failed to create directory: {e}")
        
        # Check if overwriting
        is_new = not os.path.exists(file_path)
        
        # Write file
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(params.content)
            
            # Build result message
            action = "Created" if is_new else "Updated"
            lines = params.content.count("\n") + (1 if params.content else 0)
            
            metadata = {
                "path": params.path,
                "is_new": is_new,
                "lines": lines,
                "bytes": len(params.content.encode("utf-8")),
            }
            
            return ToolResult.ok(
                f"{action} file: {params.path} ({lines} lines)",
                **metadata
            )
            
        except PermissionError:
            return ToolResult.fail(f"Permission denied: {params.path}")
        except Exception as e:
            return ToolResult.fail(f"Failed to write file: {e}")
