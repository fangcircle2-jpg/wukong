"""Glob tool - Find files matching a pattern."""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from wukong.core.tools.base import Tool, ToolResult


def _load_description() -> str:
    """Load tool description from text file."""
    desc_file = Path(__file__).parent / "glob.txt"
    if desc_file.exists():
        return desc_file.read_text(encoding="utf-8").strip()
    return "Find files matching a glob pattern."


class GlobParams(BaseModel):
    """Parameters for glob tool."""
    pattern: str = Field(description="Glob pattern to match (e.g., '**/*.py', 'src/**/*.ts')")
    path: str = Field(default=".", description="Base path to search from (relative to workspace)")
    max_results: int = Field(default=100, description="Maximum number of results to return")


class GlobTool(Tool):
    """Tool to find files matching a glob pattern.
    
    Uses Python's pathlib.glob for pattern matching.
    Supports recursive patterns with **.
    
    Examples:
        - "*.py" - All Python files in current directory
        - "**/*.py" - All Python files recursively
        - "src/**/*.ts" - All TypeScript files under src/
        - "**/test_*.py" - All test files recursively
    """
    
    name = "glob"
    description = _load_description()
    parameters = GlobParams
    
    async def execute(
        self,
        *,
        workspace_dir: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        """Find files matching a glob pattern.
        
        Args:
            workspace_dir: Workspace directory path.
            **kwargs: Tool parameters (pattern, path, max_results).
            
        Returns:
            ToolResult with matching file paths or error.
        """
        # Validate parameters
        try:
            params = self.validate_params(**kwargs)
        except Exception as e:
            return ToolResult.fail(f"Invalid parameters: {e}")
        
        # Resolve base path
        base_path = params.path
        if workspace_dir and not os.path.isabs(base_path):
            base_path = os.path.join(workspace_dir, base_path)
        
        base_path = Path(base_path)
        
        # Check base path exists
        if not base_path.exists():
            return ToolResult.fail(f"Path not found: {params.path}")
        
        if not base_path.is_dir():
            return ToolResult.fail(f"Not a directory: {params.path}")
        
        # Perform glob search
        try:
            pattern = params.pattern
            
            # If pattern doesn't start with ** and no path separator,
            # assume we want recursive search
            if not pattern.startswith("**") and "/" not in pattern and "\\" not in pattern:
                # Check if it's a simple extension pattern
                if pattern.startswith("*."):
                    pattern = "**/" + pattern
            
            matches = []
            for match in base_path.glob(pattern):
                # Get relative path from base
                try:
                    rel_path = match.relative_to(base_path)
                except ValueError:
                    rel_path = match
                
                # Format output
                if match.is_dir():
                    matches.append(f"{rel_path}/")
                else:
                    matches.append(str(rel_path))
                
                # Limit results
                if len(matches) >= params.max_results:
                    break
            
            # Build output
            if not matches:
                return ToolResult.ok(
                    f"No files matching '{params.pattern}' found in {params.path}",
                    pattern=params.pattern,
                    path=params.path,
                    count=0,
                )
            
            # Sort matches for consistent output
            matches.sort()
            
            result_text = "\n".join(matches)
            
            # Add note if results were truncated
            if len(matches) >= params.max_results:
                result_text += f"\n\n(Results truncated at {params.max_results} files)"
            
            return ToolResult.ok(
                result_text,
                pattern=params.pattern,
                path=params.path,
                count=len(matches),
            )
            
        except Exception as e:
            return ToolResult.fail(f"Glob search failed: {e}")
