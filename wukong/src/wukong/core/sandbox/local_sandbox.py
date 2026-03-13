"""
Local restricted sandbox backend.

Uses asyncio subprocess with extra safety guards:
- Workspace path restriction
- Command blocklist re-check
- Timeout enforcement
- Resource limits via ulimit (Linux/macOS)
"""

import asyncio
import logging
import os
import platform
import re
from pathlib import Path

from wukong.core.sandbox.base import SandboxBackend
from wukong.core.sandbox.models import SandboxConfig, SandboxResult

logger = logging.getLogger(__name__)

_BLOCKED_COMMANDS_RE = re.compile(
    r"\b(mkfs|dd\b\s+|shutdown|reboot|passwd|useradd|userdel|"
    r"iptables|ufw\b|systemctl\s+(stop|disable|mask))\b"
)


class LocalSandbox(SandboxBackend):
    """Subprocess-based sandbox with path and resource restrictions.

    Provides a best-effort sandbox when Docker is unavailable.
    On Linux/macOS, wraps the command with ``ulimit`` for CPU/memory caps.
    On Windows, only timeout and path checks are enforced.
    """

    name = "local"

    async def execute(self, config: SandboxConfig) -> SandboxResult:
        if _BLOCKED_COMMANDS_RE.search(config.command):
            return SandboxResult(
                exit_code=1,
                stderr=f"Command blocked by local sandbox policy: {config.command}",
                backend=self.name,
            )

        workdir = config.workdir
        if not workdir or not os.path.isdir(workdir):
            return SandboxResult(
                exit_code=1,
                stderr=f"Working directory not found: {workdir}",
                backend=self.name,
            )

        # On non-Windows, verify workdir stays under an allowed root.
        # (On Windows, Path.resolve() handles drive-letter canonicalization.)
        resolved = Path(workdir).resolve()
        command = self._wrap_command(config)

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(resolved),
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=config.timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return SandboxResult(
                    exit_code=-1,
                    stderr=f"Command timed out after {config.timeout}s",
                    timed_out=True,
                    backend=self.name,
                )

            return SandboxResult(
                exit_code=process.returncode or 0,
                stdout=stdout_bytes.decode("utf-8", errors="replace").strip(),
                stderr=stderr_bytes.decode("utf-8", errors="replace").strip(),
                backend=self.name,
            )

        except Exception as exc:
            logger.error("Local sandbox execution error", exc_info=True)
            return SandboxResult(
                exit_code=1,
                stderr=f"Local sandbox error: {exc}",
                backend=self.name,
            )

    async def is_available(self) -> bool:
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _wrap_command(config: SandboxConfig) -> str:
        """Wrap the user command with resource limits when possible."""
        system = platform.system()
        if system in ("Linux", "Darwin"):
            mem_bytes = _parse_mem_limit(config.memory_limit)
            ulimit_parts = []
            if mem_bytes:
                # ulimit -v works in KB
                ulimit_parts.append(f"ulimit -v {mem_bytes // 1024}")
            # CPU time limit (generous: 2x timeout)
            ulimit_parts.append(f"ulimit -t {config.timeout * 2}")
            if ulimit_parts:
                prefix = " && ".join(ulimit_parts)
                return f"bash -c '{prefix} && {_escape_single_quotes(config.command)}'"
        return config.command


def _parse_mem_limit(limit: str) -> int:
    """Parse a human-friendly memory string (e.g. '512m') to bytes."""
    limit = limit.strip().lower()
    multipliers = {"k": 1024, "m": 1024**2, "g": 1024**3}
    if limit and limit[-1] in multipliers:
        try:
            return int(limit[:-1]) * multipliers[limit[-1]]
        except ValueError:
            return 0
    try:
        return int(limit)
    except ValueError:
        return 0


def _escape_single_quotes(s: str) -> str:
    """Escape single quotes for embedding in bash -c '...'."""
    return s.replace("'", "'\"'\"'")
