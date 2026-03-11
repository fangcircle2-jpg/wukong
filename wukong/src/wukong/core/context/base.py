"""
Context Provider base classes.

Defines the abstract base class for all context providers,
the ContextItem data structure, and submenu items for UI selection.
"""

from abc import ABC, abstractmethod
from typing import Any
import uuid

from pydantic import BaseModel, Field


class ContextSubmenuItem(BaseModel):
    """Submenu item for provider selection UI.
    
    When user types "@file", this represents each selectable option
    in the dropdown menu.
    
    Example:
        ContextSubmenuItem(
            id="src/main.py",
            name="main.py",
            description="最近编辑",
        )
    """
    
    id: str                                    # Unique identifier (e.g., file path)
    name: str                                  # Display name (e.g., "main.py")
    description: str = ""                      # Optional description
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextItem(BaseModel):
    """Context item returned by providers.
    
    Represents actual context content to be included in LLM prompt.
    
    Example:
        ContextItem(
            id="abc123",
            provider="file",
            name="main.py",
            content="print('hello')",
            metadata={"path": "src/main.py", "language": "python"},
        )
    """
    
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    provider: str              # Provider id (e.g., "file", "url")
    name: str                  # Display name (e.g., "main.py")
    content: str               # Actual content
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextProvider(ABC):
    """Abstract base class for context providers.
    
    Providers are **stateless** - they don't hold workspace-specific state.
    The workspace_dir is passed at call time, allowing multiple sessions
    to share the same provider instance.
    
    Attributes:
        id: Unique identifier (e.g., "file")
        name: Display name (e.g., "文件")
        description: Human-readable description
        
    Example:
        class FileProvider(ContextProvider):
            id = "file"
            name = "文件"
            description = "读取本地文件内容"
            
            async def get_context(self, query: str, *, workspace_dir: str, **kwargs):
                # Read file from workspace_dir and return ContextItem
                ...
    """
    
    id: str = ""               # Unique identifier (e.g., "file")
    name: str = ""             # Display name (e.g., "文件")
    description: str = ""      # Human-readable description
    
    @abstractmethod
    async def get_context(
        self, 
        query: str,
        *,
        workspace_dir: str,
        **kwargs: Any,
    ) -> list[ContextItem]:
        """Fetch context items based on query.
        
        Args:
            query: The argument after the trigger 
                   (e.g., "src/main.py" for "@file src/main.py")
            workspace_dir: The workspace directory path (passed at runtime)
            **kwargs: Additional provider-specific arguments
            
        Returns:
            List of context items. May be empty if nothing found.
            
        Raises:
            ContextProviderError: If fetching fails (e.g., file not found)
        """
        pass
    
    async def get_submenu_items(
        self, 
        query: str = "",
        *,
        workspace_dir: str = "",
    ) -> list[ContextSubmenuItem]:
        """Get submenu items for selection UI.
        
        Called when user types "@file" to show selectable options.
        Override this to provide submenu support.
        
        Args:
            query: Optional filter string (e.g., partial filename for filtering)
            workspace_dir: The workspace directory path (passed at runtime)
            
        Returns:
            List of submenu items for user to choose from.
        """
        # Default: no submenu
        return []
    
    async def get_completions(
        self, 
        partial: str,
        *,
        workspace_dir: str = "",
    ) -> list[str]:
        """Get autocomplete suggestions for partial input.
        
        Override this to provide autocomplete support.
        
        Args:
            partial: Partial input string (e.g., "src/ma")
            workspace_dir: The workspace directory path (passed at runtime)
            
        Returns:
            List of completion suggestions.
        """
        # Default: no completions
        return []


class ContextProviderError(Exception):
    """Base exception for context provider errors."""
    
    def __init__(self, message: str, provider_id: str = ""):
        self.provider_id = provider_id
        super().__init__(f"[{provider_id}] {message}" if provider_id else message)

