"""Grep (search) tool."""

import os
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from wukong.core.tools.base import Tool, ToolResult, ToolError


def _load_description() -> str:
    """Load tool description from text file."""
    desc_file = Path(__file__).parent / "grep.txt"
    if desc_file.exists():
        return desc_file.read_text(encoding="utf-8").strip()
    return "Search for a pattern in files."


class GrepParams(BaseModel):
    """Parameters for grep tool."""
    pattern: str = Field(description="Search pattern (regex supported)")
    path: str = Field(default=".", description="File or directory path to search in")
    recursive: bool = Field(default=True, description="Search recursively in directories")
    ignore_case: bool = Field(default=False, description="Case-insensitive search")
    max_results: int = Field(default=50, description="Maximum number of results to return")
    file_pattern: str | None = Field(default=None, description="File name pattern to filter (e.g., '*.py')")


class GrepTool(Tool):
    """Tool to search for patterns in files."""
    
    name = "grep"
    description = _load_description()
    parameters = GrepParams
    
    async def execute(
        self,
        *,
        workspace_dir: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        """Search for pattern in files.
        
        Args:
            workspace_dir: Workspace directory path.
            **kwargs: Tool parameters.
            
        Returns:
            ToolResult with matching lines or error.
        """
        # Validate parameters
        try:
            params = self.validate_params(**kwargs)
        except Exception as e:
            return ToolResult.fail(f"Invalid parameters: {e}")
        
        # Resolve search path
        search_path = params.path
        if workspace_dir and not os.path.isabs(search_path):
            search_path = os.path.join(workspace_dir, search_path)
        
        # Check path exists
        if not os.path.exists(search_path):
            return ToolResult.fail(f"Path not found: {params.path}")
        
        # Compile regex
        try:
            flags = re.IGNORECASE if params.ignore_case else 0
            regex = re.compile(params.pattern, flags)
        except re.error as e:
            return ToolResult.fail(f"Invalid regex pattern: {e}")
        
        # Search
        try:
            results = []
            files_searched = 0
            
            if os.path.isfile(search_path):
                # Search single file
                matches = self._search_file(search_path, regex, params.max_results)
                results.extend(matches)
                files_searched = 1
            else:
                # Search directory
                for match in self._search_directory(
                    search_path, 
                    regex, 
                    params.recursive,
                    params.file_pattern,
                    params.max_results - len(results)
                ):
                    results.append(match)
                    files_searched = match.get("files_searched", files_searched)
                    
                    if len(results) >= params.max_results:
                        break
            
            # Format output
            if not results:
                return ToolResult.ok(
                    f"No matches found for pattern: {params.pattern}",
                    matches=0,
                    files_searched=files_searched
                )
            
            output_lines = []
            for r in results:
                # Format: file:line_num: content
                output_lines.append(f"{r['file']}:{r['line_num']}: {r['line'].rstrip()}")
            
            output = "\n".join(output_lines)
            
            truncated = len(results) >= params.max_results
            if truncated:
                output += f"\n\n... (truncated at {params.max_results} results)"
            
            return ToolResult.ok(
                output,
                matches=len(results),
                truncated=truncated
            )
            
        except Exception as e:
            return ToolResult.fail(f"Search failed: {e}")
    
    def _search_file(self, file_path: str, regex: re.Pattern, max_results: int) -> list[dict]:
        """Search for pattern in a single file."""
        results = []
        
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    if regex.search(line):
                        results.append({
                            "file": file_path,
                            "line_num": line_num,
                            "line": line,
                        })
                        
                        if len(results) >= max_results:
                            break
        except (PermissionError, IOError):
            pass  # Skip files we can't read
        
        return results
    
    def _search_directory(
        self, 
        dir_path: str, 
        regex: re.Pattern, 
        recursive: bool,
        file_pattern: str | None,
        max_results: int
    ):
        """Search for pattern in directory."""
        import fnmatch
        
        files_searched = 0
        
        if recursive:
            for root, dirs, files in os.walk(dir_path):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                
                for name in files:
                    # Skip hidden files
                    if name.startswith("."):
                        continue
                    
                    # Apply file pattern filter
                    if file_pattern and not fnmatch.fnmatch(name, file_pattern):
                        continue
                    
                    file_path = os.path.join(root, name)
                    files_searched += 1
                    
                    for match in self._search_file(file_path, regex, max_results):
                        match["files_searched"] = files_searched
                        yield match
        else:
            for name in os.listdir(dir_path):
                file_path = os.path.join(dir_path, name)
                
                if not os.path.isfile(file_path):
                    continue
                
                # Skip hidden files
                if name.startswith("."):
                    continue
                
                # Apply file pattern filter
                if file_pattern and not fnmatch.fnmatch(name, file_pattern):
                    continue
                
                files_searched += 1
                
                for match in self._search_file(file_path, regex, max_results):
                    match["files_searched"] = files_searched
                    yield match
