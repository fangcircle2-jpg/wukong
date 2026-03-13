"""
Sandbox manager.

Owns backend selection, lifecycle, and provides the unified ``execute()``
entry point consumed by BashTool.
"""

import logging
from typing import Literal

from wukong.core.sandbox.base import SandboxBackend
from wukong.core.sandbox.docker_sandbox import DockerSandbox
from wukong.core.sandbox.local_sandbox import LocalSandbox
from wukong.core.sandbox.models import SandboxConfig, SandboxResult

logger = logging.getLogger(__name__)

BackendPreference = Literal["auto", "docker", "local"]


class SandboxManager:
    """Selects and manages sandbox backends.

    Usage::

        manager = SandboxManager(backend="auto")
        await manager.initialize()

        result = await manager.execute(SandboxConfig(
            command="python -c 'print(1)'",
            workdir="/my/project",
        ))

        await manager.cleanup()
    """

    def __init__(self, backend: BackendPreference = "auto") -> None:
        self._preference = backend
        self._docker = DockerSandbox()
        self._local = LocalSandbox()
        self._active: SandboxBackend | None = None
        self._initialized = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Probe backends and select the active one."""
        if self._initialized:
            return

        if self._preference == "docker":
            if await self._docker.is_available():
                self._active = self._docker
            else:
                logger.warning("Docker requested but unavailable; no sandbox active")
        elif self._preference == "local":
            self._active = self._local
        else:
            # auto: prefer Docker, fallback to local
            if await self._docker.is_available():
                self._active = self._docker
                logger.info("Sandbox backend: docker")
            else:
                self._active = self._local
                logger.info("Docker unavailable, sandbox backend: local")

        self._initialized = True

    async def cleanup(self) -> None:
        await self._docker.cleanup()
        self._active = None
        self._initialized = False

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(self, config: SandboxConfig) -> SandboxResult:
        """Execute a command in the selected sandbox backend.

        Automatically initializes on first call if needed.
        """
        if not self._initialized:
            await self.initialize()

        if self._active is None:
            return SandboxResult(
                exit_code=1,
                stderr="No sandbox backend available",
                backend="none",
            )

        logger.debug(
            "Sandbox execute [%s]: %s", self._active.name, config.command[:120]
        )
        return await self._active.execute(config)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def active_backend(self) -> str:
        if self._active is None:
            return "none"
        return self._active.name

    @property
    def is_docker(self) -> bool:
        return isinstance(self._active, DockerSandbox)

    async def __aenter__(self) -> "SandboxManager":
        await self.initialize()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.cleanup()
