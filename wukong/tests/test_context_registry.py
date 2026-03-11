"""
Tests for ContextRegistry.

Run with: pytest tests/test_context_registry.py -v
"""

import logging
import tempfile
from pathlib import Path

import pytest

from wukong.core.context import (
    ContextProvider,
    ContextRegistry,
    FileProvider,
    create_default_registry,
)
from wukong.core.context.base import ContextItem


# ========================================
# Mock Provider for Testing
# ========================================

class MockProvider(ContextProvider):
    """Mock provider for testing (stateless)."""
    
    id = "mock"
    name = "Mock Provider"
    description = "A mock provider for testing"
    
    async def get_context(self, query: str, *, workspace_dir: str, **kwargs) -> list[ContextItem]:
        return [ContextItem(
            provider=self.id,
            name="mock_item",
            content=f"Mock content for: {query} in {workspace_dir}",
        )]


class AnotherMockProvider(ContextProvider):
    """Another mock provider with different id (stateless)."""
    
    id = "another"
    name = "Another Provider"
    description = "Another mock provider"
    
    async def get_context(self, query: str, *, workspace_dir: str, **kwargs) -> list[ContextItem]:
        return []


# ========================================
# Fixtures
# ========================================

@pytest.fixture
def registry():
    """Create an empty registry."""
    return ContextRegistry()


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        (workspace / "test.txt").write_text("test content", encoding="utf-8")
        yield workspace


# ========================================
# Test Registration
# ========================================

class TestRegistration:
    """Test provider registration."""
    
    def test_register_provider(self, registry: ContextRegistry):
        """Test registering a provider."""
        provider = MockProvider()
        result = registry.register(provider)
        
        assert result is True
        assert len(registry) == 1
        assert "mock" in registry
    
    def test_register_multiple_providers(self, registry: ContextRegistry):
        """Test registering multiple providers."""
        registry.register(MockProvider())
        registry.register(AnotherMockProvider())
        
        assert len(registry) == 2
        assert "mock" in registry
        assert "another" in registry
    
    def test_duplicate_registration_ignored(self, registry: ContextRegistry, caplog):
        """Test that duplicate registration is ignored with warning."""
        provider1 = MockProvider()
        provider2 = MockProvider()  # Same id
        
        result1 = registry.register(provider1)
        
        with caplog.at_level(logging.WARNING):
            result2 = registry.register(provider2)
        
        assert result1 is True
        assert result2 is False  # Ignored
        assert len(registry) == 1
        assert "already registered" in caplog.text
    
    def test_unregister_provider(self, registry: ContextRegistry):
        """Test unregistering a provider."""
        registry.register(MockProvider())
        
        result = registry.unregister("mock")
        
        assert result is True
        assert len(registry) == 0
        assert "mock" not in registry
    
    def test_unregister_nonexistent(self, registry: ContextRegistry, caplog):
        """Test unregistering a non-existent provider."""
        with caplog.at_level(logging.WARNING):
            result = registry.unregister("nonexistent")
        
        assert result is False
        assert "not found" in caplog.text


# ========================================
# Test Lookup
# ========================================

class TestLookup:
    """Test provider lookup."""
    
    def test_get_provider(self, registry: ContextRegistry):
        """Test getting a provider by ID."""
        provider = MockProvider()
        registry.register(provider)
        
        result = registry.get("mock")
        
        assert result is provider
    
    def test_get_nonexistent_returns_none(self, registry: ContextRegistry):
        """Test getting a non-existent provider returns None."""
        result = registry.get("nonexistent")
        
        assert result is None
    
    def test_get_all(self, registry: ContextRegistry):
        """Test getting all providers."""
        registry.register(MockProvider())
        registry.register(AnotherMockProvider())
        
        all_providers = registry.get_all()
        
        assert len(all_providers) == 2
        assert all(isinstance(p, ContextProvider) for p in all_providers)
    
    def test_has(self, registry: ContextRegistry):
        """Test has method."""
        registry.register(MockProvider())
        
        assert registry.has("mock") is True
        assert registry.has("nonexistent") is False
    
    def test_list_ids(self, registry: ContextRegistry):
        """Test listing all provider IDs."""
        registry.register(MockProvider())
        registry.register(AnotherMockProvider())
        
        ids = registry.list_ids()
        
        assert set(ids) == {"mock", "another"}


# ========================================
# Test Container Operations
# ========================================

class TestContainerOperations:
    """Test container-like operations."""
    
    def test_len(self, registry: ContextRegistry):
        """Test __len__."""
        assert len(registry) == 0
        
        registry.register(MockProvider())
        assert len(registry) == 1
    
    def test_contains(self, registry: ContextRegistry):
        """Test __contains__ (in operator)."""
        registry.register(MockProvider())
        
        assert "mock" in registry
        assert "nonexistent" not in registry
    
    def test_iter(self, registry: ContextRegistry):
        """Test __iter__."""
        registry.register(MockProvider())
        registry.register(AnotherMockProvider())
        
        providers = list(registry)
        
        assert len(providers) == 2
        assert all(isinstance(p, ContextProvider) for p in providers)
    
    def test_clear(self, registry: ContextRegistry):
        """Test clearing all providers."""
        registry.register(MockProvider())
        registry.register(AnotherMockProvider())
        
        registry.clear()
        
        assert len(registry) == 0


# ========================================
# Test Default Registration
# ========================================

class TestDefaultRegistration:
    """Test default provider registration."""
    
    def test_register_defaults(self, registry: ContextRegistry):
        """Test registering default providers (stateless)."""
        registered = registry.register_defaults()
        
        assert "file" in registered
        assert len(registry) >= 1
        assert registry.has("file")
    
    def test_register_defaults_with_filter(self, registry: ContextRegistry):
        """Test registering defaults with specific providers enabled."""
        registered = registry.register_defaults(enabled_providers=["file"])
        
        assert "file" in registered
        assert len(registry) == 1
    
    def test_register_defaults_empty_filter(self, registry: ContextRegistry):
        """Test registering defaults with empty filter registers nothing."""
        registered = registry.register_defaults(enabled_providers=[])
        
        assert registered == []
        assert len(registry) == 0
    
    def test_create_default_registry(self):
        """Test factory function (stateless, no workspace_dir needed)."""
        registry = create_default_registry()
        
        assert isinstance(registry, ContextRegistry)
        assert registry.has("file")
    
    def test_create_default_registry_with_filter(self):
        """Test factory function with enabled_providers filter."""
        registry = create_default_registry(enabled_providers=["file"])
        
        assert isinstance(registry, ContextRegistry)
        assert registry.has("file")


# ========================================
# Test Provider Integration
# ========================================

class TestProviderIntegration:
    """Test registry with real providers."""
    
    @pytest.mark.asyncio
    async def test_use_registered_provider(
        self, 
        registry: ContextRegistry, 
        temp_workspace: Path
    ):
        """Test using a registered provider (stateless, pass workspace_dir at call time)."""
        registry.register(FileProvider())  # No workspace_dir in constructor
        
        provider = registry.get("file")
        assert provider is not None
        
        # Pass workspace_dir at call time
        items = await provider.get_context("test.txt", workspace_dir=str(temp_workspace))
        
        assert len(items) == 1
        assert "test content" in items[0].content
    
    @pytest.mark.asyncio
    async def test_same_provider_multiple_workspaces(
        self,
        registry: ContextRegistry,
        temp_workspace: Path
    ):
        """Test that same provider instance works with different workspaces."""
        registry.register(FileProvider())
        
        # Create another workspace
        with tempfile.TemporaryDirectory() as tmpdir2:
            workspace2 = Path(tmpdir2)
            (workspace2 / "other.txt").write_text("other content", encoding="utf-8")
            
            provider = registry.get("file")
            
            # Use with first workspace
            items1 = await provider.get_context("test.txt", workspace_dir=str(temp_workspace))
            assert "test content" in items1[0].content
            
            # Use with second workspace (same provider instance)
            items2 = await provider.get_context("other.txt", workspace_dir=str(workspace2))
            assert "other content" in items2[0].content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
