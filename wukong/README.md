# Wukong 悟空 — CLI Agent

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-brightgreen" />
  <img src="https://img.shields.io/badge/license-MIT-green" />
  <img src="https://img.shields.io/badge/status-alpha-orange" />
</p>

High-performance AI Agent CLI for developers. Multi-LLM support, smart context management, and parallel task execution.

<p align="center">
  <a href="README.zh-CN.md">中文</a>
</p>

---

## Contents

- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Architecture](#architecture)
- [Development](#development)

---

## Features

- **Multi-LLM**: OpenAI, Anthropic Claude, Google Gemini, local Ollama, and any OpenAI-compatible API (Zhipu, Moonshot, DeepSeek, etc.) via LiteLLM
- **ReAct Loop**: Agent plans, calls tools, observes results, and iterates until done
- **Context Providers**: `@file`, `@url`, `@codebase` inject external content into the conversation
- **Batch Tool**: Run multiple sub-tasks in parallel and aggregate results
- **Session Persistence**: Local storage with resume, list, and fork
- **MCP Integration**: Model Context Protocol for external tools
- **Sandbox**: Optional Docker sandbox for sensitive commands
- **Rich TUI**: Markdown, syntax highlighting, streaming output

---

## Installation

### Prerequisites

- Python 3.11+
- (Optional) Docker for sandbox execution

### Virtual Environment (Recommended)

```bash
cd wukong

# Create venv
python -m venv .venv

# Activate
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Windows CMD:
.venv\Scripts\activate.bat
# Linux / macOS:
source .venv/bin/activate

# Install core
pip install -e .

# Install LLM support
pip install -e ".[llm]"

# Install all optional features
pip install -e ".[all]"

# Deactivate when done
deactivate
```

### Optional Dependencies

| Extra | Contents | Command |
|-------|----------|---------|
| `llm` | LiteLLM, OpenAI, Anthropic, Google | `pip install -e ".[llm]"` |
| `mcp` | MCP protocol | `pip install -e ".[mcp]"` |
| `ui` | Enhanced terminal UI (prompt-toolkit) | `pip install -e ".[ui]"` |
| `sandbox` | Docker sandbox | `pip install -e ".[sandbox]"` |
| `dev` | Tests, Lint, type check | `pip install -e ".[dev]"` |
| `all` | All production features | `pip install -e ".[all]"` |

---

## Configuration

### 1. Create `.env`

```bash
cp .env.example .env
```

### 2. Set API Keys

Edit `.env` and configure at least one LLM provider:

```bash
# Anthropic Claude (recommended)
WUKONG_LLM_PROVIDER=anthropic
WUKONG_LLM_MODEL=claude-sonnet-4-20250514
WUKONG_LLM_ANTHROPIC_API_KEY=sk-ant-your-key-here

# OpenAI
WUKONG_LLM_PROVIDER=openai
WUKONG_LLM_MODEL=gpt-4o
WUKONG_LLM_OPENAI_API_KEY=sk-your-key-here

# OpenAI-compatible (e.g. Zhipu GLM)
WUKONG_LLM_PROVIDER=openai
WUKONG_LLM_MODEL=glm-4-plus
WUKONG_LLM_OPENAI_API_KEY=your-zhipu-key
WUKONG_LLM_OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/

# Local Ollama
WUKONG_LLM_PROVIDER=local
WUKONG_LLM_LOCAL_MODEL=llama3.2
WUKONG_LLM_LOCAL_BASE_URL=http://localhost:11434/v1
```

See [.env.example](.env.example) for full options.

### 3. MCP Servers (Optional)

Configure in `~/.config/wukong/mcp_servers.json`:

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

## Usage

### Basic Commands

```bash
# Interactive chat
wukong

# Single query
wukong -q "Analyze this project's architecture"
wukong --query "Implement quicksort in Python"

# Help
wukong --help
```

### Session Management

```bash
# List sessions
wukong ls

# Resume last session
wukong resume

# Resume specific session
wukong resume --session <session-id>

# Fork current session
wukong fork

# Session subcommands
wukong session --help
```

### Context Injection

Use `@` directives in the prompt:

```
> @file:src/main.py Refactor this function
> @url:https://docs.example.com/api Generate code from this doc
> @codebase Analyze code quality
```

---

## Architecture

```
src/wukong/
├── __main__.py              # Entry point
├── cli/                     # Typer CLI
└── core/
    ├── agent/               # ReAct Agent loop
    │   └── loop.py          # Think → Act → Observe
    ├── config/              # Pydantic Settings
    │   └── settings.py      # Env var mapping
    ├── context/             # Context Provider system
    │   ├── registry.py      # Provider registration
    │   └── providers/       # file, url, codebase
    ├── llm/                 # LLM adapter layer
    │   ├── router.py        # Provider routing
    │   └── adapters/        # OpenAI, Anthropic, Google
    ├── mcp/                 # MCP integration
    ├── prompt/              # System prompts
    ├── sandbox/             # Docker sandbox
    ├── session/             # Session storage
    └── tools/               # Built-in tools
        └── builtins/        # bash, read_file, write_file, batch, etc.
```

---

## Development

```bash
# Dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run specific test file
pytest tests/test_agent_loop.py -v

# Lint
ruff check src/

# Format
ruff format src/

# Type check
mypy src/

# Pre-commit check
ruff check src/ && mypy src/ && pytest
```

### Adding a New Tool

1. Create a new file under `src/wukong/core/tools/builtins/`
2. Implement `BaseTool` (`name`, `description`, `execute`)
3. Register in the tool registry

### Adding a New Context Provider

1. Create a provider under `src/wukong/core/context/providers/`
2. Implement `BaseContextProvider`
3. Add to `ContextSettings.enabled_providers`

---

## License

[MIT](../LICENSE) © 2026 Wukong Contributors
