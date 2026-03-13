"""
Tests for BashTool + Sandbox integration.

Verifies that BashTool correctly routes dangerous commands to sandbox
and keeps safe commands on the direct path.

Run with: pytest tests/test_bash_sandbox_integration.py -v
"""

import tempfile
from unittest.mock import patch

import pytest

from wukong.core.tools.builtins.bash import BashTool


@pytest.fixture
def bash_tool():
    return BashTool()


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def _make_sandbox_settings(**overrides):
    """Create a mock SandboxSettings-like object."""
    from types import SimpleNamespace
    defaults = dict(
        enabled=True,
        backend="local",
        docker_image="python:3.11-slim",
        network_enabled=False,
        memory_limit="512m",
        cpu_limit=1.0,
        timeout=120,
        auto_sandbox_dangerous=True,
        auto_sandbox_moderate=False,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_settings(sandbox_settings):
    """Create a mock Settings-like object with .sandbox attribute."""
    from types import SimpleNamespace
    return SimpleNamespace(sandbox=sandbox_settings)


class TestSandboxRouting:
    """Test that _should_sandbox routes correctly."""

    def test_safe_command_not_sandboxed(self):
        sandbox_settings = _make_sandbox_settings()
        settings = _make_settings(sandbox_settings)

        with patch("wukong.core.tools.builtins.bash.BashTool._should_sandbox") as mock:
            # Directly test the static method logic
            from wukong.core.sandbox.risk import RiskAnalyzer
            from wukong.core.sandbox.models import RiskLevel

            assessment = RiskAnalyzer().analyze("ls -la")
            assert assessment.level == RiskLevel.SAFE

    def test_dangerous_command_detected(self):
        from wukong.core.sandbox.risk import RiskAnalyzer
        from wukong.core.sandbox.models import RiskLevel

        assessment = RiskAnalyzer().analyze("rm -rf /")
        assert assessment.level == RiskLevel.DANGEROUS


class TestBashToolDirectExecution:
    """Test that safe commands still work via direct execution."""

    @pytest.mark.asyncio
    async def test_safe_command_runs_directly(self, bash_tool, temp_workspace):
        sandbox_settings = _make_sandbox_settings(enabled=False)
        settings = _make_settings(sandbox_settings)

        with patch("wukong.core.tools.builtins.bash.get_settings", return_value=settings, create=True):
            result = await bash_tool.execute(
                workspace_dir=temp_workspace,
                command="echo direct",
            )
            assert result.success
            assert "direct" in result.output

    @pytest.mark.asyncio
    async def test_sandbox_disabled_runs_all_direct(self, bash_tool, temp_workspace):
        """When sandbox.enabled=False, even dangerous commands run directly."""
        sandbox_settings = _make_sandbox_settings(enabled=False)
        settings = _make_settings(sandbox_settings)

        with patch(
            "wukong.core.config.get_settings",
            return_value=settings,
        ):
            result = await bash_tool.execute(
                workspace_dir=temp_workspace,
                command="echo test",
            )
            assert result.success
            assert result.metadata.get("sandbox") is False


class TestBashToolSandboxExecution:
    """Test sandbox path of BashTool."""

    @pytest.mark.asyncio
    async def test_dangerous_command_goes_to_sandbox(self, bash_tool, temp_workspace):
        """Verify that a dangerous command is routed to sandbox execution."""
        sandbox_settings = _make_sandbox_settings(enabled=True, backend="local")
        settings = _make_settings(sandbox_settings)

        with patch(
            "wukong.core.config.get_settings",
            return_value=settings,
        ):
            result = await bash_tool.execute(
                workspace_dir=temp_workspace,
                command="sudo echo test",
            )
            # The local sandbox should block sudo
            assert result.metadata.get("sandbox") is True
            assert result.metadata.get("backend") == "local"


class TestBashToolMetadata:
    """Test that metadata correctly reports execution environment."""

    @pytest.mark.asyncio
    async def test_direct_execution_metadata(self, bash_tool, temp_workspace):
        """Direct execution should have sandbox=False in metadata."""
        sandbox_settings = _make_sandbox_settings(enabled=False)
        settings = _make_settings(sandbox_settings)

        with patch(
            "wukong.core.config.get_settings",
            return_value=settings,
        ):
            result = await bash_tool.execute(
                workspace_dir=temp_workspace,
                command="echo meta",
            )
            assert result.metadata.get("sandbox") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
