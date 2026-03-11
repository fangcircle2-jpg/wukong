"""
Context Providers module - Pluggable context management system.

Inspired by continue.dev's provider pattern, this module provides
various context providers for different data sources:
- FileProvider: Read file contents (@file)
- CodebaseProvider: Semantic code search (@codebase)
- FolderProvider: Directory structure (@folder)
- TerminalProvider: Terminal output (@terminal)
- URLProvider: Web page content (@url)
- GitProvider: Git diff/log (@git)

Providers are stateless - workspace_dir is passed at call time,
allowing multiple sessions to share the same registry.
"""

import logging
from typing import TYPE_CHECKING

from wukong.core.context.base import (
    ContextItem,
    ContextProvider,
    ContextProviderError,
    ContextSubmenuItem,
)
from wukong.core.context.providers import FileProvider
from wukong.core.context.registry import ContextRegistry, create_default_registry

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Global registry instance (lazy loaded)
_registry: ContextRegistry | None = None


def get_registry() -> ContextRegistry:
    """Get the global ContextRegistry singleton.
    
    Creates and initializes the registry on first call,
    registering default providers based on configuration.
    
    Returns:
        Global ContextRegistry instance.
        
    Example:
        registry = get_registry()
        file_provider = registry.get("file")
        
        # Pass workspace_dir at call time
        items = await file_provider.get_context("src/main.py", workspace_dir="/project")
    """
    global _registry
    if _registry is None:
        _registry = _create_registry_from_config()
    return _registry


def _create_registry_from_config() -> ContextRegistry:
    """Create registry from application config.
    
    Reads ContextSettings to determine which providers to enable.
    """
    # Import here to avoid circular imports
    from wukong.core.config import get_settings
    
    settings = get_settings()
    
    # Get enabled providers from config (if ContextSettings exists)
    enabled_providers = None
    if hasattr(settings, "context") and hasattr(settings.context, "enabled_providers"):
        enabled_providers = settings.context.enabled_providers
    
    registry = ContextRegistry()
    registry.register_defaults(enabled_providers=enabled_providers)
    
    logger.info(f"Initialized global context registry with providers: {registry.list_ids()}")
    return registry


def reload_registry() -> ContextRegistry:
    """Reload the global registry.
    
    Clears and recreates the registry from config.
    Useful after config changes.
    
    Returns:
        Reloaded ContextRegistry instance.
    """
    global _registry
    _registry = _create_registry_from_config()
    return _registry


__all__ = [
    # Base classes
    "ContextItem",
    "ContextProvider",
    "ContextProviderError",
    "ContextSubmenuItem",
    # Registry
    "ContextRegistry",
    "create_default_registry",
    "get_registry",
    "reload_registry",
    # Providers
    "FileProvider",
]
