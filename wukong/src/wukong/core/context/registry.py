"""
Context Provider Registry.

Manages registration and lookup of context providers.
Providers are stateless - workspace_dir is passed at call time.
"""

import logging

from wukong.core.context.base import ContextProvider

logger = logging.getLogger(__name__)


class ContextRegistry:
    """Registry for context providers.
    
    Manages provider registration, lookup, and lifecycle.
    Providers are stateless - they don't hold workspace-specific state.
    
    Usage:
        registry = ContextRegistry()
        
        # Register providers (stateless - no workspace_dir)
        registry.register(FileProvider())
        registry.register(URLProvider())
        
        # Or use defaults
        registry.register_defaults()
        
        # Lookup
        file_provider = registry.get("file")
        all_providers = registry.get_all()
        
        # Use provider (pass workspace_dir at call time)
        items = await file_provider.get_context("src/main.py", workspace_dir="/path/to/project")
    """
    
    def __init__(self):
        """Initialize empty registry."""
        self._providers: dict[str, ContextProvider] = {}
    
    def register(self, provider: ContextProvider) -> bool:
        """Register a provider.
        
        If a provider with the same id is already registered,
        the registration is ignored and a warning is logged.
        
        Args:
            provider: Provider instance to register (stateless).
            
        Returns:
            True if registered successfully, False if already exists.
        """
        if provider.id in self._providers:
            logger.warning(
                f"Provider '{provider.id}' is already registered, ignoring duplicate registration"
            )
            return False
        
        self._providers[provider.id] = provider
        logger.debug(f"Registered provider: {provider.id} ({provider.name})")
        return True
    
    def unregister(self, provider_id: str) -> bool:
        """Unregister a provider.
        
        Args:
            provider_id: ID of provider to unregister.
            
        Returns:
            True if unregistered successfully, False if not found.
        """
        if provider_id not in self._providers:
            logger.warning(f"Provider '{provider_id}' not found, cannot unregister")
            return False
        
        del self._providers[provider_id]
        logger.debug(f"Unregistered provider: {provider_id}")
        return True
    
    def get(self, provider_id: str) -> ContextProvider | None:
        """Get a provider by ID.
        
        Args:
            provider_id: Provider ID (e.g., "file", "url").
            
        Returns:
            Provider instance if found, None otherwise.
        """
        return self._providers.get(provider_id)
    
    def get_all(self) -> list[ContextProvider]:
        """Get all registered providers.
        
        Returns:
            List of all provider instances.
        """
        return list(self._providers.values())
    
    def has(self, provider_id: str) -> bool:
        """Check if a provider is registered.
        
        Args:
            provider_id: Provider ID to check.
            
        Returns:
            True if registered, False otherwise.
        """
        return provider_id in self._providers
    
    def list_ids(self) -> list[str]:
        """Get list of all registered provider IDs.
        
        Returns:
            List of provider IDs.
        """
        return list(self._providers.keys())
    
    def clear(self) -> None:
        """Clear all registered providers."""
        self._providers.clear()
        logger.debug("Cleared all providers from registry")
    
    def __len__(self) -> int:
        """Get number of registered providers."""
        return len(self._providers)
    
    def __contains__(self, provider_id: str) -> bool:
        """Check if provider is registered (supports 'in' operator)."""
        return provider_id in self._providers
    
    def __iter__(self):
        """Iterate over registered providers."""
        return iter(self._providers.values())
    
    # ========================================
    # Default Provider Registration
    # ========================================
    
    def register_defaults(self, enabled_providers: list[str] | None = None) -> list[str]:
        """Register default providers.
        
        Convenience method to register commonly used providers.
        Providers are stateless - no workspace_dir needed at registration.
        
        Currently available providers:
        - file: FileProvider
        
        More providers will be added as they are implemented.
        
        Args:
            enabled_providers: List of provider IDs to enable.
                              If None, all available providers are registered.
            
        Returns:
            List of successfully registered provider IDs.
        """
        registered = []
        
        # Default: enable all available providers
        if enabled_providers is None:
            enabled_providers = ["file"]  # Add more as implemented
        
        # Import here to avoid circular imports
        from wukong.core.context.providers.file import FileProvider
        
        # Register FileProvider
        if "file" in enabled_providers:
            if self.register(FileProvider()):
                registered.append("file")
        
        # TODO: Add more providers as they are implemented
        # if "url" in enabled_providers:
        #     if self.register(URLProvider()):
        #         registered.append("url")
        # if "codebase" in enabled_providers:
        #     if self.register(CodebaseProvider()):
        #         registered.append("codebase")
        # if "folder" in enabled_providers:
        #     if self.register(FolderProvider()):
        #         registered.append("folder")
        
        logger.info(f"Registered {len(registered)} default providers: {registered}")
        return registered


# ========================================
# Factory Function
# ========================================

def create_default_registry(enabled_providers: list[str] | None = None) -> ContextRegistry:
    """Create a registry with default providers registered.
    
    Convenience function for quick setup.
    Providers are stateless - workspace_dir is passed at call time, not here.
    
    Args:
        enabled_providers: List of provider IDs to enable.
                          If None, all available providers are registered.
        
    Returns:
        Configured ContextRegistry instance.
        
    Example:
        registry = create_default_registry()
        file_provider = registry.get("file")
        
        # Pass workspace_dir at call time
        items = await file_provider.get_context("src/main.py", workspace_dir="/project")
    """
    registry = ContextRegistry()
    registry.register_defaults(enabled_providers=enabled_providers)
    return registry
