"""
Tests for SandboxManager.

Run with: pytest tests/test_sandbox_manager.py -v
"""

import tempfile

import pytest

from wukong.core.sandbox.manager import SandboxManager
from wukong.core.sandbox.models import SandboxConfig


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestManagerBackendSelection:
    """Backend selection and fallback tests."""

    @pytest.mark.asyncio
    async def test_local_backend_explicit(self):
        async with SandboxManager(backend="local") as mgr:
            assert mgr.active_backend == "local"
            assert mgr.is_docker is False

    @pytest.mark.asyncio
    async def test_auto_backend_always_selects_something(self):
        async with SandboxManager(backend="auto") as mgr:
            assert mgr.active_backend in ("docker", "local")

    @pytest.mark.asyncio
    async def test_double_initialize_is_idempotent(self):
        mgr = SandboxManager(backend="local")
        await mgr.initialize()
        backend_1 = mgr.active_backend
        await mgr.initialize()
        backend_2 = mgr.active_backend
        assert backend_1 == backend_2
        await mgr.cleanup()


class TestManagerExecution:
    """End-to-end execution via manager."""

    @pytest.mark.asyncio
    async def test_execute_simple_command(self, temp_workspace):
        async with SandboxManager(backend="local") as mgr:
            config = SandboxConfig(command="echo manager_test", workdir=temp_workspace)
            result = await mgr.execute(config)
            assert result.exit_code == 0
            assert "manager_test" in result.stdout

    @pytest.mark.asyncio
    async def test_execute_auto_initializes(self, temp_workspace):
        mgr = SandboxManager(backend="local")
        # Don't call initialize() - execute should handle it
        config = SandboxConfig(command="echo lazy", workdir=temp_workspace)
        result = await mgr.execute(config)
        assert result.exit_code == 0
        assert "lazy" in result.stdout
        await mgr.cleanup()


class TestManagerCleanup:
    """Lifecycle and cleanup tests."""

    @pytest.mark.asyncio
    async def test_cleanup_resets_state(self):
        mgr = SandboxManager(backend="local")
        await mgr.initialize()
        assert mgr.active_backend == "local"

        await mgr.cleanup()
        assert mgr.active_backend == "none"

    @pytest.mark.asyncio
    async def test_context_manager(self, temp_workspace):
        async with SandboxManager(backend="local") as mgr:
            config = SandboxConfig(command="echo ctx", workdir=temp_workspace)
            result = await mgr.execute(config)
            assert result.success


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
