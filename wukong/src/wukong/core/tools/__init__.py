"""
Tools module - Agent tools for code operations.

Provides tools for:
- File operations (read, write, list)
- Code analysis (search, grep, AST parsing)
- Shell execution (with sandbox support)

Tools are stateless - workspace_dir is passed at execution time,
allowing multiple sessions to share the same registry.
"""

import logging
from typing import TYPE_CHECKING

from wukong.core.tools.base import (
    EmptyParameters,
    Tool,
    ToolError,
    ToolResult,
)
from wukong.core.tools.registry import ToolRegistry, create_default_registry

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Global registry instance (lazy loaded)
_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """Get the global ToolRegistry singleton.
    
    Creates and initializes the registry on first call,
    registering default tools based on configuration.
    
    Returns:
        Global ToolRegistry instance.
        
    Example:
        registry = get_registry()
        read_tool = registry.get("read_file")
        
        # Execute tool with workspace_dir at runtime
        result = await read_tool.execute(path="src/main.py", workspace_dir="/project")
    """
    global _registry
    if _registry is None:
        _registry = _create_registry_from_config()
    return _registry


def _create_registry_from_config() -> ToolRegistry:
    """Create registry from application config.
    
    Reads ToolSettings to determine which tools to enable.
    """
    # Import here to avoid circular imports
    from wukong.core.config import get_settings
    
    settings = get_settings()
    
    # Get enabled tools from config (if ToolSettings exists)
    enabled_tools = None
    if hasattr(settings, "tools") and hasattr(settings.tools, "enabled_tools"):
        enabled_tools = settings.tools.enabled_tools
    
    registry = ToolRegistry()
    registry.register_defaults(enabled_tools=enabled_tools)
    
    logger.info(f"Initialized global tool registry with tools: {registry.list_names()}")
    return registry


__all__ = [
    # Base classes
    "Tool",
    "ToolResult",
    "ToolError",
    "EmptyParameters",
    # Registry
    "ToolRegistry",
    "create_default_registry",
    "get_registry",
]
