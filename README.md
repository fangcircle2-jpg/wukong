# Wukong 悟空

<p align="center">
  <img src="https://img.shields.io/badge/version-0.1.0--alpha-blue" alt="Version" />
  <img src="https://img.shields.io/badge/python-3.11%2B-brightgreen" alt="Python" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License" />
  <img src="https://img.shields.io/badge/status-alpha-orange" alt="Status" />
</p>

<p align="center">
  High-performance AI Agent CLI for developers.<br/>
  Multi-model support, smart context injection, and parallel task execution — your terminal, supercharged.
</p>

<p align="center">
  <a href="https://fangcircle2-jpg.github.io/wukong/">🌐 Live Demo</a>
  · <a href="README.zh-CN.md">中文</a>
</p>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Multi-Model** | Seamlessly switch between OpenAI, Claude, Gemini, and local Ollama — no vendor lock-in |
| **Smart Context** | Inject project context via `@file`, `@url`, `@code` so AI truly understands your codebase |
| **Parallel Tasks** | Batch mode for concurrent task distribution and processing |
| **ReAct Loop** | Autonomous reasoning: decompose tasks, call tools, adapt strategy from feedback |
| **Safe Sandbox** | Run sensitive commands in Docker containers to protect your host |
| **MCP Support** | Model Context Protocol compatible — connect to the MCP tool ecosystem |
| **Terminal UX** | Rich-based UI with Markdown, syntax highlighting, and streaming output |

## Project Structure

```
wukong/                      # Monorepo root
├── apps/
│   └── landing/             # Next.js landing page
├── wukong/                  # Python CLI Agent
│   ├── src/wukong/
│   │   ├── cli/             # Typer CLI entry
│   │   └── core/
│   │       ├── agent/       # ReAct Agent loop
│   │       ├── config/      # Pydantic Settings
│   │       ├── context/     # Context Provider system
│   │       ├── llm/         # LLM adapter layer (LiteLLM)
│   │       ├── mcp/         # MCP protocol integration
│   │       ├── prompt/      # System Prompt management
│   │       ├── sandbox/     # Docker sandbox execution
│   │       ├── session/     # Session persistence
│   │       └── tools/       # Built-in tools
│   └── tests/
├── package.json
└── pnpm-workspace.yaml
```

## Quick Start

### CLI Agent

```bash
cd wukong

# 1. Create and activate virtual environment
python -m venv .venv

# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 2. Install dependencies (with all optional features)
pip install -e ".[all]"

# 3. Configure environment variables
cp .env.example .env
# Edit .env and add your API keys

# 4. Run
wukong --help

# Deactivate when done
deactivate
```

See [wukong/README.md](wukong/README.md) for details.

### Landing Page

- **Live**: <https://fangcircle2-jpg.github.io/wukong/>

```bash
# Install dependencies
pnpm install

# Local development
pnpm dev:landing

# Production build
pnpm build:landing
```

## Environment Variables

Copy `wukong/.env.example` to `wukong/.env` and configure:

```bash
# LLM provider
WUKONG_LLM_PROVIDER=anthropic          # openai | anthropic | google | local
WUKONG_LLM_MODEL=claude-sonnet-4-20250514

# API key for your provider
WUKONG_LLM_ANTHROPIC_API_KEY=sk-ant-...

# OpenAI-compatible APIs (Zhipu, Moonshot, DeepSeek, etc.)
# WUKONG_LLM_PROVIDER=openai
# WUKONG_LLM_OPENAI_API_KEY=your-key
# WUKONG_LLM_OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
```

Full config: [wukong/.env.example](wukong/.env.example).

## Common Commands

```bash
wukong                          # Interactive chat
wukong -q "Implement quicksort"  # Single query
wukong ls                       # List sessions
wukong resume                   # Resume last session
wukong fork                     # Fork current session
wukong session                  # Session management
```

## Development

```bash
cd wukong

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/
ruff format src/

# Type check
mypy src/
```

## Tech Stack

| Subproject | Stack |
|------------|-------|
| `wukong/` | Python 3.11+, Typer, Rich, Pydantic v2, LiteLLM, MCP |
| `apps/landing/` | Next.js 15, React 19, Tailwind CSS v4, Framer Motion |

## Contributing

Issues and PRs welcome!

1. Fork the repo
2. Create a branch: `git checkout -b feature/your-feature`
3. Commit: `git commit -m 'feat: add your feature'`
4. Push: `git push origin feature/your-feature`
5. Open a Pull Request

Please ensure:
- New features include tests
- Code passes `ruff check` and `mypy`
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/)

## License

[MIT](LICENSE) © 2026 Wukong Contributors
