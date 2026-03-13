"""
Docker-based sandbox backend.

Runs commands inside a disposable Docker container with:
- Workspace mounted (read-only by default)
- Resource limits (CPU, memory)
- Optional network isolation
- Auto-cleanup after execution
"""

import asyncio
import logging
from typing import Any

from wukong.core.sandbox.base import SandboxBackend
from wukong.core.sandbox.models import SandboxConfig, SandboxResult

logger = logging.getLogger(__name__)


class DockerSandbox(SandboxBackend):
    """Docker container sandbox.

    Requires the ``docker`` Python package (``pip install wukong[sandbox]``).
    Falls back gracefully when Docker daemon is unreachable.
    """

    name = "docker"

    def __init__(self) -> None:
        self._client: Any | None = None
        self._available: bool | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(self, config: SandboxConfig) -> SandboxResult:
        client = self._get_client()
        if client is None:
            return SandboxResult(
                exit_code=1,
                stderr="Docker client unavailable. Install docker package and start Docker daemon.",
                backend=self.name,
            )

        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                None, self._run_container, client, config
            )
            return result
        except Exception as exc:
            logger.error("Docker sandbox execution error", exc_info=True)
            return SandboxResult(
                exit_code=1,
                stderr=f"Docker sandbox error: {exc}",
                backend=self.name,
            )

    async def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        loop = asyncio.get_running_loop()
        self._available = await loop.run_in_executor(None, self._check_available)
        return self._available

    async def cleanup(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
            self._available = None

    # ------------------------------------------------------------------
    # Internals (blocking — run inside executor)
    # ------------------------------------------------------------------

    def _get_client(self) -> Any | None:
        if self._client is not None:
            return self._client
        try:
            import docker  # type: ignore[import-untyped]

            self._client = docker.from_env()
            self._client.ping()
            return self._client
        except Exception:
            logger.debug("Docker client not available", exc_info=True)
            self._available = False
            return None

    def _check_available(self) -> bool:
        try:
            client = self._get_client()
            return client is not None
        except Exception:
            return False

    def _run_container(self, client: Any, config: SandboxConfig) -> SandboxResult:
        """Synchronous helper — called via ``run_in_executor``."""
        import docker.errors  # type: ignore[import-untyped]

        volumes = self._build_volumes(config)
        nano_cpus = int(config.cpu_limit * 1e9)

        container = None
        try:
            container = client.containers.run(
                image=config.docker_image,
                command=["sh", "-c", config.command],
                working_dir="/workspace",
                volumes=volumes,
                environment=config.environment or None,
                network_mode="bridge" if config.network_enabled else "none",
                mem_limit=config.memory_limit,
                nano_cpus=nano_cpus,
                detach=True,
                stdout=True,
                stderr=True,
            )

            exit_info = container.wait(timeout=config.timeout)
            exit_code: int = exit_info.get("StatusCode", -1)
            stdout = container.logs(stdout=True, stderr=False).decode(
                "utf-8", errors="replace"
            )
            stderr = container.logs(stdout=False, stderr=True).decode(
                "utf-8", errors="replace"
            )

            return SandboxResult(
                exit_code=exit_code,
                stdout=stdout.strip(),
                stderr=stderr.strip(),
                backend=self.name,
            )

        except docker.errors.ContainerError as exc:
            return SandboxResult(
                exit_code=exc.exit_status,
                stderr=str(exc),
                backend=self.name,
            )
        except Exception as exc:
            is_timeout = "timed out" in str(exc).lower() or "read timed out" in str(exc).lower()
            if is_timeout and container is not None:
                try:
                    container.kill()
                except Exception:
                    pass
            return SandboxResult(
                exit_code=-1,
                stderr=str(exc),
                timed_out=is_timeout,
                backend=self.name,
            )
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

    @staticmethod
    def _build_volumes(config: SandboxConfig) -> dict[str, dict[str, str]]:
        """Build Docker volume mount dict."""
        mode = "ro" if config.readonly_workspace else "rw"
        volumes: dict[str, dict[str, str]] = {
            config.workdir: {"bind": "/workspace", "mode": mode},
        }
        for host_path, container_path in config.extra_mounts.items():
            volumes[host_path] = {"bind": container_path, "mode": "ro"}
        return volumes
