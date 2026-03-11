"""
File Context Provider.

Reads local file contents and provides file selection features.
Stateless design - workspace_dir is passed at call time.
"""

import asyncio
import re
from pathlib import Path
from typing import Any

from pathspec import PathSpec
from rapidfuzz import fuzz

from wukong.core.context.base import (
    ContextItem,
    ContextProvider,
    ContextProviderError,
    ContextSubmenuItem,
)


class FileProvider(ContextProvider):
    """File content provider (stateless).
    
    Features:
    - Read file contents with optional line range
    - Truncate large files (default 500 lines)
    - Recent files list (sorted by mtime)
    - Fuzzy search file names
    - Respect .gitignore rules
    
    Usage:
        provider = FileProvider()  # No workspace_dir in constructor
        
        # Read entire file (workspace_dir passed at call time)
        items = await provider.get_context("src/main.py", workspace_dir="/path/to/project")
        
        # Read specific lines
        items = await provider.get_context("src/main.py:10-50", workspace_dir="/path/to/project")
        
        # Get recent files
        submenu = await provider.get_submenu_items(workspace_dir="/path/to/project")
        
        # Fuzzy search
        submenu = await provider.get_submenu_items("main", workspace_dir="/path/to/project")
    """
    
    id = "file"
    name = "File"
    description = "Read local file contents"
    
    # Configuration constants (internal, not exposed in Config)
    MAX_LINES = 500
    SUBMENU_LIMIT = 20
    
    # Default ignore patterns (used when no .gitignore exists)
    DEFAULT_IGNORE_PATTERNS = [
        ".git/",
        "__pycache__/",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".Python",
        "node_modules/",
        ".venv/",
        "venv/",
        ".env/",
        "env/",
        "*.egg-info/",
        "dist/",
        "build/",
        ".eggs/",
        "*.so",
        "*.dylib",
        ".DS_Store",
        "Thumbs.db",
        ".idea/",
        ".vscode/",
        "*.log",
    ]
    
    # Cache for gitignore specs per workspace
    _gitignore_cache: dict[str, PathSpec] = {}
    
    async def get_context(
        self, 
        query: str,
        *,
        workspace_dir: str,
        **kwargs: Any,
    ) -> list[ContextItem]:
        """Read file content.
        
        Args:
            query: File path, optionally with line range.
                   Formats: "path/to/file.py" or "path/to/file.py:10-50"
            workspace_dir: The workspace directory path.
            **kwargs: Additional arguments (unused).
            
        Returns:
            List containing one ContextItem with file content.
            
        Raises:
            ContextProviderError: If file doesn't exist or is outside workspace.
        """
        workspace = Path(workspace_dir).resolve()
        
        # Parse query
        file_path, line_range = self._parse_query(query)
        
        # Validate path
        abs_path = self._validate_path(file_path, workspace)
        
        # Read file content (run in thread to avoid blocking)
        content, actual_start, actual_end, total_lines = await asyncio.to_thread(
            self._read_file_lines, abs_path, line_range
        )
        
        # Build relative path for display (use forward slashes for consistency)
        rel_path = abs_path.relative_to(workspace)
        rel_path_str = rel_path.as_posix()  # Always use forward slashes
        
        # Create ContextItem
        item = ContextItem(
            provider=self.id,
            name=abs_path.name,
            content=content,
            metadata={
                "path": rel_path_str,
                "extension": abs_path.suffix,
                "lines": f"{actual_start}-{actual_end}",
                "total_lines": total_lines,
            },
        )
        
        return [item]
    
    async def get_submenu_items(
        self, 
        query: str = "",
        *,
        workspace_dir: str = "",
    ) -> list[ContextSubmenuItem]:
        """Get file selection submenu.
        
        Args:
            query: Filter string for fuzzy search.
                   If empty, returns recent files.
            workspace_dir: The workspace directory path.
                   
        Returns:
            List of selectable file items.
        """
        if not workspace_dir:
            return []
        
        workspace = Path(workspace_dir).resolve()
        
        if query:
            # Fuzzy search
            files = await asyncio.to_thread(
                self._fuzzy_search_files, query, workspace, self.SUBMENU_LIMIT
            )
        else:
            # Recent files
            files = await asyncio.to_thread(
                self._get_recent_files, workspace, self.SUBMENU_LIMIT
            )
        
        items = []
        for file_path in files:
            rel_path = file_path.relative_to(workspace)
            rel_path_str = rel_path.as_posix()  # Always use forward slashes
            parent_str = rel_path.parent.as_posix() if rel_path.parent != Path(".") else ""
            items.append(ContextSubmenuItem(
                id=rel_path_str,
                name=file_path.name,
                description=parent_str,
                metadata={"extension": file_path.suffix},
            ))
        
        return items
    
    async def get_completions(
        self, 
        partial: str,
        *,
        workspace_dir: str = "",
    ) -> list[str]:
        """Get path completions.
        
        Args:
            partial: Partial path string.
            workspace_dir: The workspace directory path.
            
        Returns:
            List of matching paths.
        """
        if not partial or not workspace_dir:
            return []
        
        workspace = Path(workspace_dir).resolve()
        
        matches = await asyncio.to_thread(
            self._get_path_completions, partial, workspace, 10
        )
        return matches
    
    # ========================================
    # Private Methods
    # ========================================
    
    def _parse_query(self, query: str) -> tuple[Path, tuple[int, int] | None]:
        """Parse query into path and optional line range.
        
        Args:
            query: Query string like "path/file.py" or "path/file.py:10-50"
            
        Returns:
            Tuple of (Path, line_range or None)
        """
        # Match pattern: path:start-end
        match = re.match(r"^(.+?):(\d+)-(\d+)$", query)
        if match:
            path_str = match.group(1)
            start = int(match.group(2))
            end = int(match.group(3))
            return Path(path_str), (start, end)
        
        return Path(query), None
    
    def _validate_path(self, file_path: Path, workspace: Path) -> Path:
        """Validate and resolve file path.
        
        Args:
            file_path: Relative or absolute path.
            workspace: Workspace directory.
            
        Returns:
            Resolved absolute path.
            
        Raises:
            ContextProviderError: If path is invalid.
        """
        # Resolve to absolute
        if file_path.is_absolute():
            abs_path = file_path.resolve()
        else:
            abs_path = (workspace / file_path).resolve()
        
        # Security check: must be within workspace
        try:
            abs_path.relative_to(workspace)
        except ValueError:
            raise ContextProviderError(
                f"Path is outside workspace: {file_path}",
                provider_id=self.id,
            )
        
        # Check existence
        if not abs_path.exists():
            raise ContextProviderError(
                f"File does not exist: {file_path}",
                provider_id=self.id,
            )
        
        # Check it's a file
        if not abs_path.is_file():
            raise ContextProviderError(
                f"Not a file: {file_path}",
                provider_id=self.id,
            )
        
        return abs_path
    
    def _read_file_lines(
        self, 
        path: Path, 
        line_range: tuple[int, int] | None = None,
    ) -> tuple[str, int, int, int]:
        """Read file lines.
        
        Args:
            path: Absolute file path.
            line_range: Optional (start, end) 1-indexed line numbers.
            
        Returns:
            Tuple of (content, actual_start, actual_end, total_lines)
        """
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError as e:
            raise ContextProviderError(
                f"Cannot read file: {e}",
                provider_id=self.id,
            )
        
        total_lines = len(lines)
        
        if line_range:
            # Use specified range (1-indexed)
            start, end = line_range
            start = max(1, start)
            end = min(total_lines, end)
        else:
            # Default: from beginning, up to max_lines
            start = 1
            end = min(total_lines, self.MAX_LINES)
        
        # Extract lines (convert to 0-indexed)
        selected_lines = lines[start - 1:end]
        content = "".join(selected_lines)
        
        # Add truncation notice if needed
        if end < total_lines and line_range is None:
            content += f"\n... (truncated: {total_lines} total lines, showing first {end})"
        
        return content, start, end, total_lines
    
    def _get_gitignore_spec(self, workspace: Path) -> PathSpec:
        """Get or create gitignore spec for workspace (cached).
        
        Args:
            workspace: Workspace directory.
            
        Returns:
            PathSpec for gitignore matching.
        """
        workspace_key = str(workspace)
        
        if workspace_key in self._gitignore_cache:
            return self._gitignore_cache[workspace_key]
        
        patterns = list(self.DEFAULT_IGNORE_PATTERNS)
        gitignore_path = workspace / ".gitignore"
        
        if gitignore_path.exists():
            try:
                with open(gitignore_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        # Skip comments and empty lines
                        if line and not line.startswith("#"):
                            patterns.append(line)
            except OSError:
                pass  # Use default patterns if can't read
        
        spec = PathSpec.from_lines("gitignore", patterns)
        self._gitignore_cache[workspace_key] = spec
        return spec
    
    def _get_recent_files(self, workspace: Path, limit: int) -> list[Path]:
        """Get recently modified files sorted by mtime.
        
        Args:
            workspace: Workspace directory.
            limit: Maximum number of files to return.
            
        Returns:
            List of file paths, most recent first.
        """
        files_with_mtime: list[tuple[Path, float]] = []
        
        for file_path in self._iter_workspace_files(workspace):
            try:
                mtime = file_path.stat().st_mtime
                files_with_mtime.append((file_path, mtime))
            except OSError:
                continue
        
        # Sort by mtime (most recent first)
        files_with_mtime.sort(key=lambda x: x[1], reverse=True)
        
        return [f[0] for f in files_with_mtime[:limit]]
    
    def _fuzzy_search_files(self, query: str, workspace: Path, limit: int) -> list[Path]:
        """Fuzzy search files by name.
        
        Args:
            query: Search query.
            workspace: Workspace directory.
            limit: Maximum results.
            
        Returns:
            List of matching file paths, sorted by relevance.
        """
        scored_files: list[tuple[Path, float]] = []
        query_lower = query.lower()
        
        for file_path in self._iter_workspace_files(workspace):
            # Score based on file name (not full path)
            name_lower = file_path.name.lower()
            
            # Use partial ratio for better substring matching
            score = fuzz.partial_ratio(query_lower, name_lower)
            
            # Boost exact prefix matches
            if name_lower.startswith(query_lower):
                score += 20
            
            # Boost if query appears in path
            rel_path = str(file_path.relative_to(workspace)).lower()
            if query_lower in rel_path:
                score += 10
            
            if score > 50:  # Threshold
                scored_files.append((file_path, score))
        
        # Sort by score (highest first)
        scored_files.sort(key=lambda x: x[1], reverse=True)
        
        return [f[0] for f in scored_files[:limit]]
    
    def _get_path_completions(self, partial: str, workspace: Path, limit: int) -> list[str]:
        """Get path completions for partial input.
        
        Args:
            partial: Partial path string.
            workspace: Workspace directory.
            limit: Maximum completions.
            
        Returns:
            List of matching relative paths.
        """
        # Normalize partial to use forward slashes
        partial_normalized = partial.replace("\\", "/").lower()
        matches: list[str] = []
        
        for file_path in self._iter_workspace_files(workspace):
            rel_path = file_path.relative_to(workspace).as_posix()
            if rel_path.lower().startswith(partial_normalized):
                matches.append(rel_path)
                if len(matches) >= limit:
                    break
        
        return matches
    
    def _iter_workspace_files(self, workspace: Path):
        """Iterate over all files in workspace, respecting gitignore.
        
        Args:
            workspace: Workspace directory.
            
        Yields:
            Path objects for each file.
        """
        gitignore_spec = self._get_gitignore_spec(workspace)
        
        for file_path in workspace.rglob("*"):
            if not file_path.is_file():
                continue
            
            # Get relative path for gitignore matching
            try:
                rel_path = file_path.relative_to(workspace)
            except ValueError:
                continue
            
            # Check gitignore
            if gitignore_spec.match_file(str(rel_path)):
                continue
            
            yield file_path
