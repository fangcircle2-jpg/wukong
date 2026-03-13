"""
Tests for LocalSandbox backend.

Run with: pytest tests/test_local_sandbox.py -v
"""

import tempfile

import pytest

from wukong.core.sandbox.local_sandbox import LocalSandbox
from wukong.core.sandbox.models import SandboxConfig


@pytest.fixture
def sandbox():
    return LocalSandbox()


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestLocalSandboxExecution:
    """Basic execution tests."""

    @pytest.mark.asyncio
    async def test_simple_command(self, sandbox, temp_workspace):
        config = SandboxConfig(command="echo hello", workdir=temp_workspace)
        result = await sandbox.execute(config)
        assert result.exit_code == 0
        assert "hello" in result.stdout
        assert result.backend == "local"

    @pytest.mark.asyncio
    async def test_command_with_stderr(self, sandbox, temp_workspace):
        config = SandboxConfig(command="echo err >&2", workdir=temp_workspace)
        result = await sandbox.execute(config)
        assert result.exit_code == 0
        assert "err" in result.stderr

    @pytest.mark.asyncio
    async def test_failing_command(self, sandbox, temp_workspace):
        config = SandboxConfig(command="exit 42", workdir=temp_workspace)
        result = await sandbox.execute(config)
        assert result.exit_code == 42
        assert not result.success

    @pytest.mark.asyncio
    async def test_is_always_available(self, sandbox):
        assert await sandbox.is_available() is True


class TestLocalSandboxSafety:
    """Safety and restriction tests."""

    @pytest.mark.asyncio
    async def test_blocked_command_rejected(self, sandbox, temp_workspace):
        config = SandboxConfig(command="shutdown -h now", workdir=temp_workspace)
        result = await sandbox.execute(config)
        assert result.exit_code == 1
        assert "blocked" in result.stderr.lower()

    @pytest.mark.asyncio
    async def test_mkfs_blocked(self, sandbox, temp_workspace):
        config = SandboxConfig(command="mkfs.ext4 /dev/sda", workdir=temp_workspace)
        result = await sandbox.execute(config)
        assert result.exit_code == 1

    @pytest.mark.asyncio
    async def test_nonexistent_workdir(self, sandbox):
        config = SandboxConfig(command="echo test", workdir="/nonexistent/path/xyz")
        result = await sandbox.execute(config)
        assert result.exit_code == 1
        assert "not found" in result.stderr.lower()


class TestLocalSandboxTimeout:
    """Timeout enforcement tests."""

    @pytest.mark.asyncio
    async def test_timeout_kills_command(self, sandbox, temp_workspace):
        import sys
        if sys.platform == "win32":
            cmd = "ping -n 30 127.0.0.1"
        else:
            cmd = "sleep 30"

        config = SandboxConfig(command=cmd, workdir=temp_workspace, timeout=1)
        result = await sandbox.execute(config)
        assert result.timed_out is True
        assert result.exit_code == -1


class TestSandboxResult:
    """Test SandboxResult properties."""

    @pytest.mark.asyncio
    async def test_output_property(self, sandbox, temp_workspace):
        config = SandboxConfig(
            command="echo out && echo err >&2",
            workdir=temp_workspace,
        )
        result = await sandbox.execute(config)
        output = result.output
        assert "out" in output
        assert "[stderr]" in output
        assert "err" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
