"""
Prompt builder for System Prompt construction.

Combines base prompt, mode prompt, and dynamic context into a complete system prompt.
"""

from __future__ import annotations

import platform
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from wukong.core.session.models import MessageMode

if TYPE_CHECKING:
    from wukong.core.llm.schema import ToolDefinition


# Map MessageMode to template file names
MODE_TEMPLATE_MAP: dict[MessageMode, str] = {
    MessageMode.NORMAL: "ask.md",    # NORMAL -> Ask mode
    MessageMode.PLAN: "plan.md",
    MessageMode.CODE: "agent.md",    # CODE -> Agent mode
}

# Map LLM provider to base template
PROVIDER_TEMPLATE_MAP: dict[str, str] = {
    "anthropic": "claude.md",
    "openai": "openai.md",
    "google": "default.md",
    "local": "default.md",
    "mock": "default.md",
}


class PromptBuilder:
    """
    System Prompt builder.
    
    Combines multiple prompt components:
    1. Base Prompt (per model type)
    2. Mode Prompt (ask/plan/agent)
    3. Environment Info (workspace, time, project type)
    4. Tools Description
    5. User Rules (.wukong/rules.md)
    """
    
    def __init__(
        self,
        workspace_dir: Path | str,
        mode: MessageMode = MessageMode.NORMAL,
        provider: str = "anthropic",
        custom_system_prompt: str | None = None,
    ):
        """
        Initialize PromptBuilder.
        
        Args:
            workspace_dir: Project workspace directory
            mode: Current message mode (NORMAL/PLAN/CODE)
            provider: LLM provider name (for base template selection)
            custom_system_prompt: Optional custom system prompt to use instead of templates.
                                 If provided, skips base/mode templates and uses this directly.
        """
        self.workspace_dir = Path(workspace_dir)
        self.mode = mode
        self.provider = provider
        self.templates_dir = Path(__file__).parent / "templates"
        self.custom_system_prompt = custom_system_prompt
    
    def build(self, tools: list["ToolDefinition"] | None = None) -> str:
        """
        Build complete System Prompt.
        
        Args:
            tools: List of available tools
            
        Returns:
            Complete system prompt string
        """
        # If custom system prompt is provided, use it with environment info
        if self.custom_system_prompt:
            parts = [
                self.custom_system_prompt,
                self._build_environment_info(),
                self._build_tools_section(tools),
            ]
            return "\n\n---\n\n".join(filter(None, parts))
        
        # Otherwise use template-based prompt
        parts = [
            self._load_base_prompt(),
            self._load_mode_prompt(),
            self._build_environment_info(),
            self._build_tools_section(tools),
            self._load_user_rules(),
        ]
        
        # Filter out None/empty parts and join with separator
        return "\n\n---\n\n".join(filter(None, parts))
    
    def _load_base_prompt(self) -> str:
        """Load base prompt template for current provider."""
        template_name = PROVIDER_TEMPLATE_MAP.get(self.provider, "default.md")
        template_path = self.templates_dir / "base" / template_name
        
        # Fallback to default if provider-specific doesn't exist
        if not template_path.exists():
            template_path = self.templates_dir / "base" / "default.md"
        
        return self._read_template(template_path)
    
    def _load_mode_prompt(self) -> str:
        """Load mode-specific prompt template."""
        template_name = MODE_TEMPLATE_MAP.get(self.mode, "ask.md")
        template_path = self.templates_dir / "modes" / template_name
        
        return self._read_template(template_path)
    
    def _build_environment_info(self) -> str:
        """Build dynamic environment information."""
        now = datetime.now()
        
        lines = [
            "## Environment",
            "",
            f"- Working Directory: `{self.workspace_dir}`",
            f"- Current Time: {now.strftime('%Y-%m-%d %H:%M')}",
            f"- Platform: {self._detect_platform()}",
        ]
        
        # Detect project type
        project_type = self._detect_project_type()
        if project_type:
            lines.append(f"- Project Type: {project_type}")
        
        return "\n".join(lines)
    
    def _build_tools_section(self, tools: list["ToolDefinition"] | None) -> str | None:
        """Build tools description section from template.
        
        Loads tools.md template and replaces {{tools_list}} with actual tool names.
        Full tool definitions are passed via the LLM API's tools parameter,
        so the system prompt focuses on usage guidelines rather than schemas.
        """
        if not tools:
            return None
        
        tool_names = [t.function.name for t in tools]
        tools_list = ", ".join(f"`{name}`" for name in tool_names)
        
        template_path = self.templates_dir / "tools.md"
        template = self._read_template(template_path)
        
        if template:
            return template.replace("{{tools_list}}", tools_list)
        
        return f"## Available Tools\n\n{tools_list}"
    
    def _load_user_rules(self) -> str | None:
        """Load user-defined rules from .wukong/rules.md."""
        rules_path = self.workspace_dir / ".wukong" / "rules.md"
        
        if not rules_path.exists():
            return None
        
        try:
            rules_content = rules_path.read_text(encoding="utf-8").strip()
            if not rules_content:
                return None
            
            return f"## User Rules\n\n{rules_content}"
        except Exception:
            return None
    
    def _read_template(self, path: Path) -> str:
        """Read template file content."""
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            return ""
    
    def _detect_platform(self) -> str:
        """Detect current platform."""
        return f"{platform.system()} {platform.release()}"
    
    def _detect_project_type(self) -> str | None:
        """Detect project type based on config files."""
        detectors: list[tuple[str, str]] = [
            ("pyproject.toml", "Python"),
            ("setup.py", "Python"),
            ("package.json", "Node.js"),
            ("Cargo.toml", "Rust"),
            ("go.mod", "Go"),
            ("pom.xml", "Java (Maven)"),
            ("build.gradle", "Java (Gradle)"),
            ("CMakeLists.txt", "C/C++ (CMake)"),
            ("Makefile", "Make"),
        ]
        
        for filename, project_type in detectors:
            if (self.workspace_dir / filename).exists():
                return project_type
        
        return None
    
    def set_mode(self, mode: MessageMode) -> None:
        """Update the current mode."""
        self.mode = mode
    
    def set_provider(self, provider: str) -> None:
        """Update the LLM provider."""
        self.provider = provider

