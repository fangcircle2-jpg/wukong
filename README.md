# 悟空 Wukong

<p align="center">
  <img src="https://img.shields.io/badge/version-0.1.0--alpha-blue" alt="Version" />
  <img src="https://img.shields.io/badge/python-3.11%2B-brightgreen" alt="Python" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License" />
  <img src="https://img.shields.io/badge/status-alpha-orange" alt="Status" />
</p>

<p align="center">
  专为开发者打造的高性能 AI Agent CLI 工具。<br/>
  集成多模型适配、智能上下文注入与并行任务执行，让你的终端进化为全能开发助手。
</p>

---

## ✨ 核心特性

| 特性 | 说明 |
|------|------|
| **多模型适配** | 无缝切换 OpenAI、Claude、Gemini 及本地 Ollama 模型，不被任何供应商绑定 |
| **智能上下文** | 通过 `@file`、`@url`、`@code` 快速注入项目背景，让 AI 真正理解你的代码库 |
| **并行任务执行** | Batch 模式支持多任务并发分发与处理，大幅提升自动化效率 |
| **ReAct 推理循环** | 具备自主推理能力，自动拆解复杂任务、调用工具并根据反馈调整策略 |
| **安全沙箱** | 支持在 Docker 容器中执行敏感命令，保护宿主机系统安全 |
| **MCP 协议支持** | 兼容 Model Context Protocol，可接入丰富的外部工具生态 |
| **极客终端体验** | 基于 Rich 构建，支持 Markdown 渲染、语法高亮与实时流式输出 |

## 项目结构

```
wukong/                      # Monorepo 根目录
├── apps/
│   └── landing/             # Next.js 产品落地页
├── wukong/                  # Python CLI Agent 主工程
│   ├── src/wukong/
│   │   ├── cli/             # Typer CLI 入口
│   │   └── core/
│   │       ├── agent/       # ReAct Agent 循环
│   │       ├── config/      # Pydantic Settings 配置
│   │       ├── context/     # 上下文 Provider 系统
│   │       ├── llm/         # LLM 适配层 (LiteLLM)
│   │       ├── mcp/         # MCP 协议集成
│   │       ├── prompt/      # System Prompt 管理
│   │       ├── sandbox/     # Docker 沙箱执行
│   │       ├── session/     # 会话持久化
│   │       └── tools/       # 内置工具集
│   └── tests/
├── package.json             # pnpm workspace 配置
└── pnpm-workspace.yaml
```

## 快速开始

### CLI Agent（主工程）

```bash
cd wukong

# 1. 创建并激活虚拟环境
python -m venv .venv

# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 2. 安装依赖（含所有可选特性）
pip install -e ".[all]"

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 API Key

# 4. 启动
wukong --help

# 退出虚拟环境（使用完毕后）
deactivate
```

详见 [wukong/README.md](wukong/README.md)

### 落地页（Landing Page）

```bash
# 安装依赖
pnpm install

# 本地开发
pnpm dev:landing

# 生产构建
pnpm build:landing
```

## 环境变量配置

复制 `wukong/.env.example` 为 `wukong/.env` 并填写以下关键配置：

```bash
# 选择 LLM provider
WUKONG_LLM_PROVIDER=anthropic          # openai | anthropic | google | local
WUKONG_LLM_MODEL=claude-sonnet-4-20250514

# 填入对应 provider 的 API Key
WUKONG_LLM_ANTHROPIC_API_KEY=sk-ant-...

# 使用 OpenAI 兼容接口（智谱、Moonshot、DeepSeek 等）
# WUKONG_LLM_PROVIDER=openai
# WUKONG_LLM_OPENAI_API_KEY=your-key
# WUKONG_LLM_OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
```

完整配置说明见 [wukong/.env.example](wukong/.env.example)。

## 常用命令

```bash
wukong                          # 交互式对话
wukong -q "帮我写个快速排序"     # 单次查询
wukong ls                       # 列出所有会话
wukong resume                   # 恢复上一次会话
wukong fork                     # 从当前会话创建分支
wukong session                  # 会话管理
```

## 开发指南

```bash
cd wukong

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码检查
ruff check src/
ruff format src/

# 类型检查
mypy src/
```

## 技术栈

| 子项目 | 技术 |
|--------|------|
| `wukong/` | Python 3.11+, Typer, Rich, Pydantic v2, LiteLLM, MCP |
| `apps/landing/` | Next.js 15, React 19, Tailwind CSS v4, Framer Motion |

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 提交改动：`git commit -m 'feat: add your feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 创建 Pull Request

请确保：
- 新功能附带对应测试
- 代码通过 `ruff check` 和 `mypy` 检查
- Commit message 遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范

## License

[MIT](LICENSE) © 2026 Wukong Contributors
