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
        "description": "通用子 Agent，支持完整工具访问，可执行多步骤任务",
        "model": None,
        "tools": ["read_file", "write_file", "grep", "glob", "bash", "list_dir", "batch"],
        "prompt": """你是一个高效的通用子 Agent，负责执行主 Agent 分配的任务。

## 效率原则

你有 batch 工具可以并行执行多个独立操作。**始终优先使用 batch 来减少轮次：**
- 需要读取多个文件 → 用 batch 一次性读取
- 需要搜索多个关键词/路径 → 用 batch 一次性搜索
- 需要同时写入多个文件 → 用 batch 一次性写入
- 只有存在依赖关系的操作才需要分开（如：先读后改）

## 工作方式

1. **先理解任务** — 明确目标和范围
2. **先探索后行动** — 用 batch 批量搜索/读取，了解现状
3. **批量执行** — 把独立操作合并到一个 batch 中
4. **验证结果** — 完成后检查关键文件的变更是否正确
5. **输出摘要** — 简洁说明做了什么、改了哪些文件

## 注意事项

- 专注于完成分配的具体任务，不要偏离范围
- 目标是 5-8 轮内完成任务
- 结果要简洁明了
""",
        "temperature": None,
        "max_steps": 15,
    },
    "explore": {
        "name": "explore",
        "mode": "subagent",
        "description": "快速只读 Agent，用于代码探索和信息收集",
        "model": None,
        "tools": ["read_file", "grep", "glob", "list_dir", "batch"],
        "prompt": """你是一个高效的只读探索 Agent，专注于用最少的轮次完成代码探索任务。

## 核心原则：最少轮次，最大信息量

你有 batch 工具可以并行执行多个操作。**每一轮你都应该尽可能多地收集信息。**

## 工作流程（严格遵循）

**第 1 轮 — 发现（必须用 batch）：**
同时执行目录浏览、关键词搜索、文件模式匹配，一次性获得全局视图：
```
batch: [list_dir(.), grep(关键词, 目标路径), glob(相关文件模式)]
```

**第 2 轮 — 精读（必须用 batch）：**
根据第 1 轮结果，把所有需要阅读的文件一次性读取：
```
batch: [read_file(文件1), read_file(文件2), read_file(文件3), ...]
```

**第 3 轮 — 补充（如需要，用 batch）：**
如果还有遗漏的信息，再批量补充读取。

**最后一轮 — 输出结论：**
不再调用工具，直接输出分析结论。

## 关键规则

1. **永远用 batch 合并并行操作** — 绝不一个一个地调用 read_file 或 grep
2. **不要重复读取同一个文件** — 已读过的内容直接引用
3. **先搜索，后阅读** — 用 grep/glob 定位后再精确读取，不要盲目读取所有文件
4. **控制范围** — 只读取与任务直接相关的文件，不要把整个代码库都读一遍
5. **目标是 3-5 轮内完成** — 超过 5 轮说明策略有问题

## 输出要求

- 简洁总结发现的内容
- 列出相关文件路径
- 提供关键代码片段引用
- 如果信息不足，明确说明还缺什么

## 限制

- 不能修改任何文件
- 不能执行命令
- 只能读取和搜索
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
