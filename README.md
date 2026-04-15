# MyAgent

高效的终端 AI 编程助手 — 文件读写、CLI 执行、记忆存储、自我进化。

基于 ReAct 推理引擎，支持多种国产大模型（智谱 GLM、通义千问）和本地 Ollama 部署，通过 Tool Calling 实现真实的系统交互能力。

## 特性

- **ReAct 推理引擎** — Think → Act → Observe → Decide 循环，支持多步工具调用
- **6 种意图识别** — 研究、实施、调查、评估、修复、重构，自动路由处理策略
- **4 种内置工具** — 文件读写、Shell 执行、文件名搜索、内容正则搜索
- **3 层记忆系统** — 即时记忆（对话）、工作记忆（Todo + 当前文件）、长期记忆（Markdown 持久化）
- **自我进化** — 经验记录、技能自动创建、对话模式分析
- **安全机制** — 风险评估、提示注入检测、隐形 Unicode 检测、高危险操作确认
- **多 Provider 支持** — 智谱 GLM、通义千问、OpenAI 兼容、Ollama 本地/远程部署
- **富终端 UI** — Rich 渲染（Markdown、代码高亮、表格）+ Prompt Toolkit（历史搜索、快捷键）
- **会话管理** — JSONL 持久化、上下文窗口自动裁剪

## 环境要求

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) 包管理器

## 安装

```bash
git clone https://github.com/zhang57zhang/My_Agent.git
cd My_Agent/myagent
uv sync
```

## 快速开始

### 智谱 GLM

```bash
uv run python -m myagent --provider zhipu --api-key YOUR_API_KEY
```

### 通义千问

```bash
uv run python -m myagent --provider qwen --api-key YOUR_API_KEY
```

### Ollama（本地）

```bash
# 确保 Ollama 已启动
ollama serve

# 使用默认模型 (qwen2.5)
uv run python -m myagent --provider ollama

# 指定模型
uv run python -m myagent --provider ollama --model qwen2.5:14b
```

### Ollama（远程服务器）

```bash
uv run python -m myagent --provider ollama --ollama-host 192.168.1.100 --ollama-port 11434
```

## CLI 参数

```
usage: myagent [-h] [-v] [-c CONFIG] [-w WORKDIR] [--provider PROVIDER]
               [--model MODEL] [--api-key API_KEY]
               [--ollama-host OLLAMA_HOST] [--ollama-port OLLAMA_PORT]

选项:
  -v, --verbose            启用详细日志
  -c, --config CONFIG      配置文件路径
  -w, --workdir WORKDIR    工作目录（默认当前目录）
  --provider PROVIDER      LLM Provider (zhipu/qwen/ollama)
  --model MODEL            模型 ID
  --api-key API_KEY        API Key（也可通过环境变量 MYAGENT_API_KEY 设置）
  --ollama-host HOST       Ollama 服务地址（默认 localhost）
  --ollama-port PORT       Ollama 服务端口（默认 11434）
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `MYAGENT_API_KEY` | 默认 Provider 的 API Key |
| `MYAGENT_OLLAMA_HOST` | Ollama 服务地址 |
| `MYAGENT_OLLAMA_PORT` | Ollama 服务端口 |

## 配置文件

配置文件路径: `~/.myagent/config.yaml`（首次运行自动创建）

```yaml
# 全局默认 Provider
default_provider: zhipu

# Provider 配置
providers:
  zhipu:
    provider_id: zhipu
    model_id: glm-4-plus
    api_key: "your_zhipu_key"
  qwen:
    provider_id: qwen
    model_id: qwen-plus
    api_key: "your_qwen_key"
  ollama:
    provider_id: ollama
    model_id: qwen2.5:14b
    base_url: "http://192.168.1.100:11434/v1"

# Ollama 专用
ollama_host: "localhost"
ollama_port: 11434
ollama_timeout: 120.0

# 记忆
max_memory_tokens: 800
max_context_messages: 50

# 工具安全
default_risk_level: "low"
require_confirmation_for_high_risk: true

# 自我进化
auto_create_skills: true
min_tool_calls_for_skill: 5
```

## 交互命令

在 MyAgent 对话中输入 `/` 前缀使用命令：

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助信息 |
| `/tools` | 列出所有可用工具 |
| `/info` | 显示当前会话和配置信息 |
| `/memory` | 显示当前记忆状态 |
| `/sessions` | 列出所有会话 |
| `/history` | 显示当前会话对话历史 |
| `/clear` | 清空当前会话历史 |
| `/quit` | 退出 MyAgent |

## 内置工具

| 工具 | 功能 |
|------|------|
| `file` | 文件读取、写入、编辑、目录列表 |
| `bash` | Shell 命令执行（含危险命令检测） |
| `glob` | 文件名模式搜索（如 `**/*.py`） |
| `grep` | 文件内容正则搜索 |

## 项目结构

```
src/myagent/
├── __main__.py              # CLI 入口
├── core/                    # 核心模块
│   ├── models.py            # 数据模型（Message, ToolDefinition, ProviderConfig 等）
│   └── config.py            # 配置管理（YAML + Pydantic）
├── providers/               # LLM Provider 层
│   ├── base.py              # Provider Protocol + 异常定义
│   ├── openai_compat.py     # OpenAI 兼容适配器基类
│   ├── zhipu.py             # 智谱 GLM
│   ├── qwen.py              # 通义千问
│   ├── ollama.py            # Ollama 本地/远程
│   └── registry.py          # Provider 注册表
├── tools/                   # 工具系统
│   ├── base.py              # Tool Protocol + ToolRegistry
│   └── builtins/            # 内置工具
│       ├── file_tool.py     # 文件操作
│       ├── bash_tool.py     # Shell 执行
│       ├── glob_tool.py     # 文件名搜索
│       └── grep_tool.py     # 内容搜索
├── memory/                  # 3 层记忆系统
│   ├── conversation.py      # 即时记忆（对话历史）
│   ├── working.py           # 工作记忆（Todo + 当前文件）
│   ├── longterm.py          # 长期记忆（Markdown 持久化）
│   └── manager.py           # 记忆管理器
├── engine/                  # 推理引擎
│   ├── intent.py            # 意图识别（6 种类型）
│   └── react.py             # ReAct 循环引擎
├── sessions/                # 会话管理
│   └── manager.py           # JSONL 持久化
├── ui/                      # 终端界面
│   └── terminal.py          # Rich + Prompt Toolkit
├── evolution/               # 自我进化
│   └── manager.py           # 经验记录 + 技能创建
└── safety/                  # 安全模块
    └── checker.py           # 风险评估 + 注入检测
```

## 依赖

### 运行时依赖

| 包 | 用途 |
|----|------|
| `openai` | LLM API 客户端（Provider 通用） |
| `pydantic` | 数据模型与配置验证 |
| `rich` | 终端富文本渲染 |
| `prompt-toolkit` | 交互式输入处理 |
| `pyyaml` | YAML 配置文件解析 |
| `aiofiles` | 异步文件操作 |
| `watchdog` | 文件系统监控 |

### 开发依赖（可选）

```bash
uv sync --extra dev
```

| 包 | 用途 |
|----|------|
| `pytest` | 测试框架 |
| `pytest-asyncio` | 异步测试支持 |
| `pytest-cov` | 测试覆盖率 |
| `ruff` | 代码检查与格式化 |
| `mypy` | 静态类型检查 |

## 端到端测试

```bash
# 使用智谱 GLM 测试
uv run python e2e_runner.py --provider zhipu --api-key YOUR_KEY

# 使用 Ollama 测试
uv run python e2e_runner.py --provider ollama
```

测试覆盖全部 10 个模块、35 个源文件的核心功能场景。

## 数据目录

MyAgent 运行时数据存储在 `~/.myagent/` 下：

```
~/.myagent/
├── config.yaml             # 用户配置
├── history.txt             # 输入历史
├── longterm-memory.md      # 长期记忆
├── sessions/               # 会话记录（JSONL）
├── skills/                 # 自动创建的技能
└── lessons-learned/        # 经验教训
```

## 技术栈

- **语言**: Python 3.12+
- **包管理**: uv
- **LLM SDK**: OpenAI Python SDK（统一接口）
- **终端渲染**: Rich + Prompt Toolkit
- **数据校验**: Pydantic v2
- **配置格式**: YAML

## License

MIT
