"""
Tests for DockerSandbox backend.

These tests require a running Docker daemon.
Run with: pytest tests/test_docker_sandbox.py -v -m docker

Skip automatically when Docker is not available.
"""

import tempfile
from pathlib import Path

import pytest

from wukong.core.sandbox.docker_sandbox import DockerSandbox
from wukong.core.sandbox.models import SandboxConfig


@pytest.fixture
async def sandbox():
    s = DockerSandbox()
    yield s
    await s.cleanup()


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


async def _docker_available() -> bool:
    s = DockerSandbox()
    result = await s.is_available()
    await s.cleanup()
    return result


docker = pytest.mark.skipif(
    "not _docker_available",
    reason="Docker daemon not available",
)


# Use a custom marker so users can opt-in: pytest -m docker
pytestmark = pytest.mark.docker


class TestDockerSandboxAvailability:
    """Availability detection tests."""

    @pytest.mark.asyncio
    async def test_is_available_returns_bool(self):
        s = DockerSandbox()
        result = await s.is_available()
        assert isinstance(result, bool)
        await s.cleanup()


class TestDockerSandboxExecution:
    """Execution tests (require Docker)."""

    @pytest.mark.asyncio
    async def test_simple_echo(self, sandbox, temp_workspace):
        if not await sandbox.is_available():
            pytest.skip("Docker not available")

        config = SandboxConfig(
            command="echo hello from docker",
            workdir=temp_workspace,
        )
        result = await sandbox.execute(config)
        assert result.exit_code == 0
        assert "hello from docker" in result.stdout
        assert result.backend == "docker"

    @pytest.mark.asyncio
    async def test_workspace_is_mounted(self, sandbox, temp_workspace):
        if not await sandbox.is_available():
            pytest.skip("Docker not available")

        marker = Path(temp_workspace) / "test_marker.txt"
        marker.write_text("sandbox_test")

        config = SandboxConfig(
            command="cat /workspace/test_marker.txt",
            workdir=temp_workspace,
        )
        result = await sandbox.execute(config)
        assert result.exit_code == 0
        assert "sandbox_test" in result.stdout

    @pytest.mark.asyncio
    async def test_network_isolation(self, sandbox, temp_workspace):
        if not await sandbox.is_available():
            pytest.skip("Docker not available")

        config = SandboxConfig(
            command="ping -c 1 -W 1 8.8.8.8",
            workdir=temp_workspace,
            network_enabled=False,
        )
        result = await sandbox.execute(config)
        # With network disabled, ping should fail
        assert result.exit_code != 0

    @pytest.mark.asyncio
    async def test_failing_command(self, sandbox, temp_workspace):
        if not await sandbox.is_available():
            pytest.skip("Docker not available")

        config = SandboxConfig(
            command="exit 42",
            workdir=temp_workspace,
        )
        result = await sandbox.execute(config)
        assert result.exit_code == 42

    @pytest.mark.asyncio
    async def test_stderr_captured(self, sandbox, temp_workspace):
        if not await sandbox.is_available():
            pytest.skip("Docker not available")

        config = SandboxConfig(
            command="echo err >&2",
            workdir=temp_workspace,
        )
        result = await sandbox.execute(config)
        assert "err" in result.stderr


class TestDockerSandboxWhenUnavailable:
    """Graceful degradation when Docker is not installed."""

    @pytest.mark.asyncio
    async def test_execute_without_docker_returns_error(self):
        s = DockerSandbox()
        if await s.is_available():
            pytest.skip("Docker IS available - cannot test unavailable path")
        
        config = SandboxConfig(command="echo test", workdir="/tmp")
        result = await s.execute(config)
        assert result.exit_code == 1
        assert "unavailable" in result.stderr.lower() or "error" in result.stderr.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "docker"])
