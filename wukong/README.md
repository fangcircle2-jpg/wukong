# 悟空 Wukong — CLI Agent

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-brightgreen" />
  <img src="https://img.shields.io/badge/license-MIT-green" />
  <img src="https://img.shields.io/badge/status-alpha-orange" />
</p>

专为开发者打造的高性能 AI Agent CLI 工具，支持多 LLM 提供商、智能上下文管理与并行任务执行。

---

## 目录

- [特性](#特性)
- [安装](#安装)
- [配置](#配置)
- [使用方法](#使用方法)
- [架构概览](#架构概览)
- [开发](#开发)

---

## 特性

- **多 LLM 适配**：通过 LiteLLM 支持 OpenAI、Anthropic Claude、Google Gemini、本地 Ollama 及任何 OpenAI 兼容接口（智谱、Moonshot、DeepSeek 等）
- **ReAct 推理循环**：Agent 能自主规划、调用工具、观察结果并反复迭代，直至任务完成
- **上下文 Provider 系统**：`@file`、`@url`、`@codebase` 等指令将外部内容注入对话上下文
- **并行 Batch 工具**：单次调用并行分发多个子任务，自动聚合结果
- **会话持久化**：对话记录本地存储，支持恢复、列出、分支（fork）等操作
- **MCP 协议集成**：兼容 Model Context Protocol，可连接任意 MCP 服务器扩展工具能力
- **安全沙箱**：可选 Docker 沙箱执行代码，隔离危险操作
- **精美 TUI**：基于 Rich 的富文本终端 UI，支持 Markdown、代码高亮与流式输出

---

## 安装

### 前置条件

- Python 3.11 或更高版本
- （可选）Docker（用于沙箱执行功能）

### 使用虚拟环境（推荐）

```bash
# 进入主工程目录
cd wukong

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Windows CMD:
.venv\Scripts\activate.bat
# Linux / macOS:
source .venv/bin/activate

# 安装核心依赖
pip install -e .

# 安装 LLM 支持
pip install -e ".[llm]"

# 安装所有可选特性
pip install -e ".[all]"

# 退出虚拟环境（使用完毕后）
# Windows / Linux / macOS 通用：
deactivate
```

### 可选依赖说明

| Extra | 包含内容 | 命令 |
|-------|---------|------|
| `llm` | LiteLLM、OpenAI、Anthropic、Google | `pip install -e ".[llm]"` |
| `mcp` | MCP 协议支持 | `pip install -e ".[mcp]"` |
| `ui` | 增强终端 UI (prompt-toolkit) | `pip install -e ".[ui]"` |
| `sandbox` | Docker 沙箱执行 | `pip install -e ".[sandbox]"` |
| `dev` | 测试、Lint、类型检查工具 | `pip install -e ".[dev]"` |
| `all` | 所有生产特性（不含 dev） | `pip install -e ".[all]"` |

---

## 配置

### 1. 创建 `.env` 文件

```bash
cp .env.example .env
```

### 2. 填写 API Key

编辑 `.env`，至少配置一个 LLM provider：

```bash
# 使用 Anthropic Claude（推荐）
WUKONG_LLM_PROVIDER=anthropic
WUKONG_LLM_MODEL=claude-sonnet-4-20250514
WUKONG_LLM_ANTHROPIC_API_KEY=sk-ant-your-key-here

# 或使用 OpenAI
WUKONG_LLM_PROVIDER=openai
WUKONG_LLM_MODEL=gpt-4o
WUKONG_LLM_OPENAI_API_KEY=sk-your-key-here

# 或使用 OpenAI 兼容接口（如智谱 GLM）
WUKONG_LLM_PROVIDER=openai
WUKONG_LLM_MODEL=glm-4-plus
WUKONG_LLM_OPENAI_API_KEY=your-zhipu-key
WUKONG_LLM_OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/

# 或使用本地 Ollama
WUKONG_LLM_PROVIDER=local
WUKONG_LLM_LOCAL_MODEL=llama3.2
WUKONG_LLM_LOCAL_BASE_URL=http://localhost:11434/v1
```

完整配置项说明见 [.env.example](.env.example)。

### 3. 配置 MCP 服务器（可选）

在 `~/.config/wukong/mcp_servers.json` 中配置 MCP 服务器：

```json
{
  "servers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/workspace"]
    }
  }
}
```

---

## 使用方法

### 基本命令

```bash
# 启动交互式对话
wukong

# 发送单次查询
wukong -q "帮我分析这个项目的架构"
wukong --query "写一个快速排序的 Python 实现"

# 查看帮助
wukong --help
```

### 会话管理

```bash
# 列出所有历史会话
wukong ls

# 恢复上一次会话
wukong resume

# 选择特定会话恢复
wukong resume --session <session-id>

# 从当前会话创建分支（保留历史，开启新对话）
wukong fork

# 会话管理子命令
wukong session --help
```

### 上下文注入

在对话中使用 `@` 指令注入上下文：

```
> @file:src/main.py 帮我重构这个函数
> @url:https://docs.example.com/api 根据这份文档帮我写代码
> @codebase 分析整个项目的代码质量
```

---

## 架构概览

```
src/wukong/
├── __main__.py              # 程序入口
├── cli/                     # Typer CLI 命令定义
└── core/
    ├── agent/               # ReAct Agent 主循环
    │   └── loop.py          # Think → Act → Observe 循环
    ├── config/              # Pydantic Settings 配置管理
    │   └── settings.py      # 所有配置项（环境变量映射）
    ├── context/             # 上下文 Provider 系统
    │   ├── registry.py      # Provider 注册与解析
    │   └── providers/       # file, url, codebase 等实现
    ├── llm/                 # LLM 适配层
    │   ├── router.py        # Provider 路由
    │   └── adapters/        # OpenAI, Anthropic, Google 适配器
    ├── mcp/                 # MCP 协议集成
    ├── prompt/              # System Prompt 管理
    ├── sandbox/             # Docker 沙箱执行
    ├── session/             # 会话存储与管理
    └── tools/               # 内置工具集
        └── builtins/        # bash, read_file, write_file, batch 等
```

---

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_agent_loop.py -v

# 代码 Lint
ruff check src/

# 代码格式化
ruff format src/

# 类型检查
mypy src/

# 一键检查（推荐提交前运行）
ruff check src/ && mypy src/ && pytest
```

### 添加新工具

1. 在 `src/wukong/core/tools/builtins/` 下创建新工具文件
2. 实现 `BaseTool` 接口（`name`、`description`、`execute` 方法）
3. 在工具注册表中注册新工具

### 添加新 Context Provider

1. 在 `src/wukong/core/context/providers/` 下创建新 Provider
2. 实现 `BaseContextProvider` 接口
3. 在 `ContextSettings.enabled_providers` 中添加名称

---

## License

[MIT](../LICENSE) © 2026 Wukong Contributors
