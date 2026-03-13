"""Bash tool - Execute shell commands with optional sandbox routing."""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from wukong.core.tools.base import Tool, ToolResult

logger = logging.getLogger(__name__)


def _load_description() -> str:
    """Load tool description from text file."""
    desc_file = Path(__file__).parent / "bash.txt"
    if desc_file.exists():
        return desc_file.read_text(encoding="utf-8").strip()
    return "Execute shell commands."


class BashParams(BaseModel):
    """Parameters for bash tool."""
    command: str = Field(description="The shell command to execute")
    workdir: str = Field(default="", description="Working directory for command execution (relative to workspace)")
    timeout: int = Field(default=120000, description="Command timeout in milliseconds")


class BashTool(Tool):
    """Tool to execute shell commands.
    
    Runs commands in a subprocess and captures output.
    Supports timeout and working directory configuration.
    When sandbox is enabled, dangerous commands are automatically
    routed to the sandbox backend (Docker or local restricted).
    
    Examples:
        - "ls -la" - List files in detail
        - "git status" - Check git status
        - "python --version" - Check Python version
        - "npm install" - Install npm packages
    """
    
    name = "bash"
    description = _load_description()
    parameters = BashParams
    
    async def execute(
        self,
        *,
        workspace_dir: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a shell command.
        
        Args:
            workspace_dir: Workspace directory path.
            **kwargs: Tool parameters (command, working_dir, timeout).
            
        Returns:
            ToolResult with command output or error.
        """
        try:
            params = self.validate_params(**kwargs)
        except Exception as e:
            return ToolResult.fail(f"Invalid parameters: {e}")
        
        cwd = self._resolve_workdir(params.workdir, workspace_dir)
        if cwd is None:
            return ToolResult.fail(
                f"Working directory not found: {params.workdir or workspace_dir}"
            )
        
        if self._should_sandbox(params.command):
            return await self._execute_sandboxed(params, cwd)
        
        return await self._execute_direct(params, cwd)

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    @staticmethod
    def _should_sandbox(command: str) -> bool:
        """Decide whether this command should run in a sandbox."""
        try:
            from wukong.core.config import get_settings
            settings = get_settings().sandbox
        except Exception:
            return False

        if not settings.enabled:
            return False

        from wukong.core.sandbox.risk import RiskAnalyzer
        from wukong.core.sandbox.models import RiskLevel

        assessment = RiskAnalyzer().analyze(command)

        if assessment.level == RiskLevel.DANGEROUS and settings.auto_sandbox_dangerous:
            logger.info("Routing to sandbox (dangerous): %s", assessment.reason)
            return True
        if assessment.level == RiskLevel.MODERATE and settings.auto_sandbox_moderate:
            logger.info("Routing to sandbox (moderate): %s", assessment.reason)
            return True

        return False

    # ------------------------------------------------------------------
    # Direct execution (original behaviour)
    # ------------------------------------------------------------------

    @staticmethod
    async def _execute_direct(params: BashParams, cwd: str) -> ToolResult:
        try:
            process = await asyncio.create_subprocess_shell(
                params.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            
            timeout_seconds = params.timeout / 1000
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout_seconds,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult.fail(
                    f"Command timed out after {params.timeout}ms",
                    command=params.command,
                    timeout=params.timeout,
                )
            
            stdout_text = stdout.decode("utf-8", errors="replace").strip()
            stderr_text = stderr.decode("utf-8", errors="replace").strip()
            
            exit_code = process.returncode
            output = _format_output(stdout_text, stderr_text, exit_code)
            
            return ToolResult.ok(
                output,
                command=params.command,
                exit_code=exit_code,
                cwd=cwd,
                sandbox=False,
            )
            
        except Exception as e:
            return ToolResult.fail(f"Command execution failed: {e}")

    # ------------------------------------------------------------------
    # Sandbox execution
    # ------------------------------------------------------------------

    @staticmethod
    async def _execute_sandboxed(params: BashParams, cwd: str) -> ToolResult:
        from wukong.core.config import get_settings
        from wukong.core.sandbox.manager import SandboxManager
        from wukong.core.sandbox.models import SandboxConfig

        settings = get_settings().sandbox
        timeout_sec = min(params.timeout // 1000, settings.timeout)

        config = SandboxConfig(
            command=params.command,
            workdir=cwd,
            timeout=timeout_sec,
            memory_limit=settings.memory_limit,
            cpu_limit=settings.cpu_limit,
            network_enabled=settings.network_enabled,
            docker_image=settings.docker_image,
        )

        manager = SandboxManager(backend=settings.backend)
        try:
            result = await manager.execute(config)
        finally:
            await manager.cleanup()

        if result.timed_out:
            return ToolResult.fail(
                f"Command timed out after {timeout_sec}s (sandbox: {result.backend})",
                command=params.command,
                timeout=timeout_sec,
                sandbox=True,
                backend=result.backend,
            )

        output = _format_output(result.stdout, result.stderr, result.exit_code)

        if result.success:
            return ToolResult.ok(
                output,
                command=params.command,
                exit_code=result.exit_code,
                cwd=cwd,
                sandbox=True,
                backend=result.backend,
            )
        return ToolResult.fail(
            output,
            command=params.command,
            exit_code=result.exit_code,
            cwd=cwd,
            sandbox=True,
            backend=result.backend,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_workdir(workdir: str, workspace_dir: str) -> str | None:
        cwd = workdir
        if cwd:
            if workspace_dir and not os.path.isabs(cwd):
                cwd = os.path.join(workspace_dir, cwd)
        else:
            cwd = workspace_dir or os.getcwd()
        return cwd if os.path.isdir(cwd) else None


def _format_output(stdout: str, stderr: str, exit_code: int | None) -> str:
    parts: list[str] = []
    if stdout:
        parts.append(stdout)
    if stderr:
        prefix = "\n[stderr]\n" if stdout else "[stderr]\n"
        parts.append(f"{prefix}{stderr}")
    output = "\n".join(parts) if parts else "(no output)"
    if exit_code and exit_code != 0:
        output += f"\n\n[exit code: {exit_code}]"
    return output
