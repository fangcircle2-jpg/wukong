"""
Sandbox backend abstract base class.

All sandbox backends (Docker, local restricted) implement this interface.
"""

from abc import ABC, abstractmethod

from wukong.core.sandbox.models import SandboxConfig, SandboxResult


class SandboxBackend(ABC):
    """Abstract base class for sandbox execution backends."""

    name: str = ""

    @abstractmethod
    async def execute(self, config: SandboxConfig) -> SandboxResult:
        """Execute a command inside the sandbox.

        Args:
            config: Execution configuration (command, limits, mounts, etc.)

        Returns:
            SandboxResult with stdout/stderr/exit_code.
        """

    @abstractmethod
    async def is_available(self) -> bool:
        """Check whether this backend is usable on the current system."""

    async def cleanup(self) -> None:
        """Release any resources held by this backend.

        Default implementation is a no-op; override if the backend
        keeps long-lived resources (e.g. container pools).
        """
