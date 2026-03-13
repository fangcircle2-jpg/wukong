"""
Sandbox data models.

Defines risk levels, execution configuration, and result types
shared across all sandbox components.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Command risk classification."""

    SAFE = "safe"
    MODERATE = "moderate"
    DANGEROUS = "dangerous"


class RiskAssessment(BaseModel):
    """Result of command risk analysis."""

    level: RiskLevel = RiskLevel.SAFE
    reason: str = ""
    matched_pattern: str = ""


class SandboxConfig(BaseModel):
    """Configuration for a single sandbox execution."""

    command: str
    workdir: str = "/workspace"
    timeout: int = Field(default=120, description="Timeout in seconds")

    # Resource limits
    memory_limit: str = "512m"
    cpu_limit: float = 1.0

    # Isolation
    network_enabled: bool = False
    readonly_workspace: bool = True

    # Docker-specific
    docker_image: str = "python:3.11-slim"
    extra_mounts: dict[str, str] = Field(
        default_factory=dict,
        description="Extra host:container mount mappings",
    )
    environment: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables to set in sandbox",
    )


class SandboxResult(BaseModel):
    """Result of sandbox execution."""

    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    backend: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    @property
    def output(self) -> str:
        """Combined output similar to BashTool format."""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            prefix = "\n[stderr]\n" if self.stdout else "[stderr]\n"
            parts.append(f"{prefix}{self.stderr}")
        return "\n".join(parts) if parts else "(no output)"
