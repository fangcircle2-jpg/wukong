"""
Agent configuration system.

Provides models and loaders for agent configurations stored in YAML format.
Configurations are stored in `.wukong/agents/` directory.
"""

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AgentConfig(BaseModel):
    """Agent configuration model.
    
    Defines the configuration for a subagent that can be invoked
    by the Task Tool.
    
    Attributes:
        name: Unique identifier for the agent.
        mode: Agent mode ("primary" or "subagent").
        description: Brief description of the agent's purpose.
        model: Optional model override (e.g., "gpt-4", "claude-3").
        tools: List of tool names available to this agent.
        prompt: System prompt for the agent.
        temperature: Optional temperature setting for LLM.
        max_steps: Maximum number of tool call iterations.
    """
    
    name: str
    mode: str = Field(default="subagent", description="Agent mode: 'primary' or 'subagent'")
    description: str = Field(default="", description="Brief description of the agent")
    model: str | None = Field(default=None, description="Optional model override")
    tools: list[str] = Field(default_factory=list, description="List of available tool names")
    prompt: str = Field(default="", description="System prompt for the agent")
    temperature: float | None = Field(default=None, description="LLM temperature setting")
    max_steps: int | None = Field(default=None, description="Maximum tool call iterations")
    
    def is_subagent(self) -> bool:
        """Check if this is a subagent configuration."""
        return self.mode == "subagent"
    
    def is_primary(self) -> bool:
        """Check if this is a primary agent configuration."""
        return self.mode == "primary"


# Default agent configurations (built-in)
DEFAULT_AGENTS: dict[str, dict[str, Any]] = {
    "general": {
        "name": "general",
        "mode": "subagent",
        "description": "General-purpose subagent with full tool access for multi-step tasks",
        "model": None,
        "tools": ["read_file", "write_file", "grep", "glob", "bash", "list_dir", "batch"],
        "prompt": """You are an efficient general-purpose subagent that executes tasks assigned by the main agent.

## Efficiency Principles

You have the batch tool to run multiple independent operations in parallel. **Always prefer batch to reduce rounds:**
- Need to read multiple files → use batch to read them at once
- Need to search multiple keywords/paths → use batch to search at once
- Need to write multiple files → use batch to write at once
- Only split operations when there are dependencies (e.g., read then modify)

## Workflow

1. **Understand the task** — Clarify goals and scope
2. **Explore before acting** — Use batch to search/read and understand the current state
3. **Execute in batch** — Merge independent operations into a single batch
4. **Verify results** — Check that key file changes are correct
5. **Output summary** — Briefly describe what was done and which files were changed

## Notes

- Focus on the assigned task, do not deviate
- Aim to complete in 5–8 rounds
- Keep results concise
""",
        "temperature": None,
        "max_steps": 15,
    },
    "explore": {
        "name": "explore",
        "mode": "subagent",
        "description": "Fast read-only agent for code exploration and information gathering",
        "model": None,
        "tools": ["read_file", "grep", "glob", "list_dir", "batch"],
        "prompt": """You are an efficient read-only exploration agent focused on completing code exploration in the fewest rounds.

## Core Principle: Fewest Rounds, Maximum Information

You have the batch tool to run multiple operations in parallel. **Each round you should gather as much information as possible.**

## Workflow (Follow Strictly)

**Round 1 — Discovery (must use batch):**
Run directory listing, keyword search, and file pattern matching in one go:
```
batch: [list_dir(.), grep(keyword, target_path), glob(file_pattern)]
```

**Round 2 — Deep Read (must use batch):**
Based on round 1, read all needed files at once:
```
batch: [read_file(file1), read_file(file2), read_file(file3), ...]
```

**Round 3 — Supplement (if needed, use batch):**
If information is missing, batch-read additional files.

**Final Round — Output Conclusion:**
No more tool calls; output your analysis directly.

## Key Rules

1. **Always use batch for parallel ops** — Never call read_file or grep one by one
2. **Do not re-read the same file** — Reference already-read content
3. **Search first, then read** — Use grep/glob to locate, then read precisely; do not blindly read all files
4. **Control scope** — Only read files directly relevant to the task; do not read the entire codebase
5. **Aim for 3–5 rounds** — More than 5 rounds indicates a strategy problem

## Output Requirements

- Summarize findings concisely
- List relevant file paths
- Provide key code snippet references
- If information is insufficient, state what is missing

## Restrictions

- Cannot modify any files
- Cannot execute commands
- Read and search only
""",
        "temperature": None,
        "max_steps": 10,
    },
}


class AgentConfigLoader:
    """Loader for agent configurations.
    
    Loads agent configurations from YAML files in the `.wukong/agents/` directory.
    Falls back to built-in default configurations if file not found.
    
    Example:
        loader = AgentConfigLoader("/path/to/workspace")
        config = loader.load("general")
        if config:
            print(config.tools)
    """
    
    AGENTS_DIR = ".wukong/agents"
    
    def __init__(self, workspace_dir: str | Path):
        """Initialize the config loader.
        
        Args:
            workspace_dir: Path to the workspace directory.
        """
        self.workspace_dir = Path(workspace_dir)
        self.agents_dir = self.workspace_dir / self.AGENTS_DIR
    
    def load(self, agent_name: str) -> AgentConfig | None:
        """Load agent configuration by name.
        
        First tries to load from YAML file, then falls back to built-in defaults.
        
        Args:
            agent_name: Name of the agent to load.
            
        Returns:
            AgentConfig if found, None otherwise.
        """
        # Try to load from YAML file first
        config = self._load_from_file(agent_name)
        if config is not None:
            return config
        
        # Fall back to built-in defaults
        return self._load_from_defaults(agent_name)
    
    def _load_from_file(self, agent_name: str) -> AgentConfig | None:
        """Load configuration from YAML file.
        
        Args:
            agent_name: Name of the agent (without .yaml extension).
            
        Returns:
            AgentConfig if file exists and is valid, None otherwise.
        """
        yaml_path = self.agents_dir / f"{agent_name}.yaml"
        yml_path = self.agents_dir / f"{agent_name}.yml"
        
        # Try .yaml first, then .yml
        config_path = yaml_path if yaml_path.exists() else yml_path
        
        if not config_path.exists():
            return None
        
        try:
            with open(config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            if data is None:
                logger.warning(f"Empty agent config file: {config_path}")
                return None
            
            # Ensure name is set
            if "name" not in data:
                data["name"] = agent_name
            
            return AgentConfig.model_validate(data)
            
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse agent config {config_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load agent config {config_path}: {e}")
            return None
    
    def _load_from_defaults(self, agent_name: str) -> AgentConfig | None:
        """Load configuration from built-in defaults.
        
        Args:
            agent_name: Name of the agent.
            
        Returns:
            AgentConfig if found in defaults, None otherwise.
        """
        if agent_name not in DEFAULT_AGENTS:
            return None
        
        return AgentConfig.model_validate(DEFAULT_AGENTS[agent_name])
    
    def list_agents(self) -> list[str]:
        """List all available agent names.
        
        Combines both file-based and built-in default agents.
        
        Returns:
            List of agent names (deduplicated).
        """
        agents = set(DEFAULT_AGENTS.keys())
        
        # Add agents from files
        if self.agents_dir.exists():
            for path in self.agents_dir.glob("*.yaml"):
                agents.add(path.stem)
            for path in self.agents_dir.glob("*.yml"):
                agents.add(path.stem)
        
        return sorted(agents)
    
    def list_subagents(self) -> list[AgentConfig]:
        """List all available subagent configurations.
        
        Returns:
            List of AgentConfig objects for subagents only.
        """
        subagents = []
        for name in self.list_agents():
            config = self.load(name)
            if config and config.is_subagent():
                subagents.append(config)
        return subagents
    
    def ensure_agents_dir(self) -> None:
        """Ensure the agents directory exists."""
        self.agents_dir.mkdir(parents=True, exist_ok=True)
