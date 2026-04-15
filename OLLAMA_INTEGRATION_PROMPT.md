# MyAgent — Ollama Provider 接入开发提示词 v1.0

> 目标：为 MyAgent 增加通过 Ollama 的 IP 地址连接本地/远程 LLM 的能力
> 前置条件：已阅读项目现有 Provider 架构（providers/ 模块）
> 预期产出：1 个新 Provider 文件 + 若干配置/CLI/测试改动

---

## 第一部分：需求概述

### 1.1 用户场景

用户在本地或远程服务器上运行了 Ollama 服务，希望 MyAgent 能够：
1. 通过 Ollama 的 IP 地址（如 `http://192.168.1.100:11434`）直接连接
2. 使用 Ollama 上拉取的任意模型（如 `llama3`, `qwen2.5`, `deepseek-coder`, `mistral` 等）
3. 享受与云端 Provider（智谱/通义）完全一致的 Agent 体验（工具调用、流式输出、记忆等）
4. 无需 API Key（Ollama 本地部署默认无认证）

### 1.2 核心要求

- **最小改动原则**：充分利用现有 `OpenAICompatProvider` 基类，改动尽量少
- **零配置启动**：Ollama 默认 `localhost:11434`，用户只需 `--provider ollama` 即可启动
- **完整功能**：支持 tool calling（function calling）、流式输出、token 统计
- **健壮性**：连接检测、模型自动发现、优雅降级（模型不支持 tool calling 时退化为纯文本）

---

## 第二部分：技术背景

### 2.1 Ollama OpenAI 兼容性

Ollama 原生提供 OpenAI 兼容 API：

```
Base URL: http://<host>:<port>/v1
默认端口: 11434
认证:      无（api_key 传任意值即可，或传 "ollama"）
```

关键端点：
```
POST   /v1/chat/completions    — 与 OpenAI 完全一致
POST   /v1/models              — 列出本地可用模型
```

### 2.2 Function Calling 支持

Ollama 从 v0.1.28+ 开始支持 OpenAI 格式的 tool/function calling，但：
- **不是所有模型都支持**：取决于模型本身的能力
- 部分小模型（如 7B 以下）可能无法稳定返回结构化 tool_calls
- 建议在运行时检测：如果模型返回的 tool_calls 解析失败，退化为纯文本模式

### 2.3 与现有架构的关系

```
Provider (Protocol)
    └── OpenAICompatProvider (共享基类，使用 AsyncOpenAI SDK)
            ├── ZhipuProvider    (PROVIDER_ID="zhipu",  base_url=智谱)
            ├── QwenProvider     (PROVIDER_ID="qwen",   base_url=通义)
            ├── OpenAICompatProvider (PROVIDER_ID="openai", base_url=OpenAI)
            └── OllamaProvider   (PROVIDER_ID="ollama", base_url=Ollama) ← 新增
```

Ollama Provider 只需继承 `OpenAICompatProvider`，设置 3 个类常量即可。

---

## 第三部分：详细实现规格

### 3.1 新增文件：`src/myagent/providers/ollama.py`

```python
"""Ollama Provider 适配器.

Ollama 提供原生 OpenAI 兼容 API：
- Base URL: http://localhost:11434/v1
- 支持模型: llama3, qwen2.5, deepseek-coder, mistral 等所有 Ollama 模型
- 认证: 无需 API Key（传任意值即可）
"""
```

**实现要点：**

```python
class OllamaProvider(OpenAICompatProvider):
    PROVIDER_ID = "ollama"
    DEFAULT_MODEL = "llama3"          # 或 "qwen2.5"，取用户最常用的
    DEFAULT_BASE_URL = "http://localhost:11434/v1"
```

**构造函数差异**：
- `api_key` 参数应设为可选（默认 `"ollama"`），因为 Ollama 不需要真实 API Key
- 需要支持自定义 `base_url`（用于连接远程 Ollama 实例）
- 建议增加 `timeout` 参数（本地推理可能较慢，默认 120s）
- 通过 `httpx.AsyncClient` 传入自定义超时和 SSL 配置

```python
import httpx
from openai import AsyncOpenAI

def __init__(
    self,
    *,
    model: str | None = None,
    api_key: str = "ollama",          # 默认值，无需真实 Key
    base_url: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    top_p: float = 0.9,
    timeout: float = 120.0,            # Ollama 推理可能较慢
    ssl_verify: bool = True,           # 自签名证书场景下可关闭
) -> None:
    # ... 赋值省略
    
    # 使用自定义 httpx 客户端控制超时和 SSL
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=10.0),
        verify=ssl_verify,
    )
    self._client = AsyncOpenAI(
        api_key=self._api_key,
        base_url=base_url or self.DEFAULT_BASE_URL,
        http_client=http_client,
    )
```

**连接检测方法**（新增，其他 Provider 不需要）：

```python
async def check_connection(self) -> dict:
    """检测 Ollama 服务是否可达，返回状态信息.
    
    Returns:
        {
            "reachable": bool,
            "host": str,
            "version": str | None,     # Ollama 版本
            "models": list[str],       # 可用模型列表
        }
    
    实现方式：
    1. GET /api/tags 获取模型列表（Ollama 原生 API，比 /v1/models 返回更多信息）
    2. 如果请求失败，返回 {"reachable": False, ...}
    3. 注意：此方法使用独立的 httpx 客户端，不依赖 OpenAI SDK
    """
```

**模型列表方法**（新增）：

```python
async def list_models(self) -> list[str]:
    """列出 Ollama 上所有可用模型.
    
    Returns:
        模型名称列表，如 ["llama3:latest", "qwen2.5:14b", "deepseek-coder:6.7b"]
    
    实现方式：
    方式1（推荐）: GET /api/tags → 解析 response["models"][*]["name"]
    方式2（兼容）: GET /v1/models → 解析 OpenAI 格式 response["data"][*]["id"]
    """

### 3.2 修改文件：`src/myagent/providers/registry.py`

在 `_REGISTRY` 中注册 Ollama：

```python
from myagent.providers.ollama import OllamaProvider

_REGISTRY: dict[str, type[OpenAICompatProvider]] = {
    "zhipu": ZhipuProvider,
    "qwen": QwenProvider,
    "openai": OpenAICompatProvider,
    "ollama": OllamaProvider,        # ← 新增
}
```

### 3.3 修改文件：`src/myagent/providers/__init__.py`

导出 OllamaProvider：

```python
from myagent.providers.ollama import OllamaProvider

__all__ = [
    # ... 现有导出
    "OllamaProvider",
]
```

### 3.4 修改文件：`src/myagent/core/config.py`

Ollama 特有配置项：

```python
class MyAgentConfig(BaseModel):
    # ... 现有字段
    
    # Ollama 专用
    ollama_host: str = "localhost"        # Ollama 主机地址
    ollama_port: int = 11434              # Ollama 端口
    ollama_timeout: float = 120.0          # 请求超时（秒）
```

### 3.5 修改文件：`src/myagent/__main__.py`

CLI 参数增强：

```python
# 新增 CLI 参数
parser.add_argument(
    "--ollama-host",
    type=str,
    default=None,
    help="Ollama 服务地址（IP 或域名），默认 localhost",
)
parser.add_argument(
    "--ollama-port",
    type=int,
    default=None,
    help="Ollama 服务端口，默认 11434",
)
```

在 provider 初始化逻辑中：
- 当 `--provider ollama` 时，自动拼接 `base_url = http://{host}:{port}/v1`
- Ollama 不需要 API Key，跳过 `api_key` 检查（或使用默认值 `"ollama"`）
- 启动时可选：打印 Ollama 连接状态和可用模型列表

```python
# Ollama 专用逻辑
if config.default_provider == "ollama":
    host = args.ollama_host or config.ollama_host
    port = args.ollama_port or config.ollama_port
    base_url = f"http://{host}:{port}/v1"
    
    # Ollama 不需要真实 API Key
    if not provider_cfg.get("api_key"):
        provider_cfg["api_key"] = "ollama"
    
    # 可选：启动时检测连接
    provider = create_provider(ProviderConfig(
        provider_id="ollama",
        model_id=provider_cfg.get("model_id", "llama3"),
        api_key="ollama",
        base_url=base_url,
        timeout=config.ollama_timeout,
    ))
```

### 3.6 修改文件：`src/myagent/core/models.py`

`ProviderConfig` 可能需要增加 `timeout` 字段（如果 OpenAICompatProvider 要支持自定义超时）：

```python
class ProviderConfig(BaseModel):
    provider_id: str
    model_id: str
    api_key: str
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.9
    timeout: float | None = None        # ← 新增，Ollama 用
```

---

## 第四部分：配置文件格式

### 4.1 `~/.myagent/config.yaml` 示例

```yaml
# 全局默认 Provider
default_provider: ollama

# Ollama 专用配置
ollama_host: "192.168.1.100"     # 远程 Ollama 服务器
ollama_port: 11434
ollama_timeout: 120.0

# Provider 详细配置
providers:
  ollama:
    provider_id: ollama
    model_id: "qwen2.5:14b"      # 使用的模型
    api_key: "ollama"             # 占位，无实际作用
  zhipu:
    provider_id: zhipu
    model_id: "glm-4-plus"
    api_key: "xxx"
```

### 4.2 环境变量支持

```
MYAGENT_OLLAMA_HOST=192.168.1.100
MYAGENT_OLLAMA_PORT=11434
```

### 4.3 CLI 启动方式

```bash
# 本地 Ollama（默认）
uv run python -m myagent --provider ollama

# 本地 Ollama + 指定模型
uv run python -m myagent --provider ollama --model qwen2.5:14b

# 远程 Ollama
uv run python -m myagent --provider ollama --ollama-host 192.168.1.100

# 远程 Ollama + 自定义端口
uv run python -m myagent --provider ollama --ollama-host 192.168.1.100 --ollama-port 8080
```

---

## 第五部分：边界情况与错误处理

### 5.1 连接失败

**场景**：Ollama 服务未启动或网络不通

**处理**：
- 启动时调用 `check_connection()` 预检
- 连接失败时给出明确错误信息：
  ```
  [错误] 无法连接到 Ollama 服务 (192.168.1.100:11434)
  请确认：
  1. Ollama 已启动: ollama serve
  2. 地址和端口正确
  3. 防火墙允许连接
  ```
- `_call_with_retry` 中的连接错误应映射为 `ProviderError`，不触发无意义重试

### 5.2 模型不存在

**场景**：用户指定的模型未拉取

**处理**：
- API 返回 404 或模型错误时，提示可用模型列表：
  ```
  [错误] 模型 "mistral:latest" 不存在
  可用模型: llama3:latest, qwen2.5:14b, deepseek-coder:6.7b
  使用方法: ollama pull mistral
  ```

### 5.3 Tool Calling 不支持

**场景**：使用不支持 function calling 的小模型

**处理**：
- 第一次 tool call 请求失败时，记录日志警告
- 退化为"纯文本 + 正则提取"模式：在 system prompt 中用文本格式描述工具，让模型用自然语言"调用"
- 或直接提示用户切换到支持 tool calling 的模型

### 5.4 推理超时

**场景**：大模型在慢设备上推理时间超过 timeout

**处理**：
- 默认 timeout 设为 120s（比云 API 的 60s 更长）
- 超时后在 UI 中提示，建议用户使用更小的模型或增加 timeout
- 不自动重试超时请求（推理请求天然幂等但耗时长）

### 5.5 SSL/自签名证书

**场景**：远程 Ollama 配置了 HTTPS 自签名证书

**处理**：
- 在 `AsyncOpenAI` 中传入 `http_client` 配置 `verify=False`
- 可通过配置项 `ollama_ssl_verify: bool = True` 控制
- 记录安全警告日志

---

## 第六部分：测试提示词

### T-Ollama-01: 连接检测

```
启动 MyAgent 连接 Ollama，然后问我：Ollama 服务状态如何？有哪些可用模型？
```

**预期结果**：
- 调用 `check_connection()` 检测连接
- 列出 Ollama 上所有可用模型
- 显示 Ollama 版本号

**验证标准**：
- [ ] 成功连接 Ollama 服务
- [ ] 返回非空的模型列表
- [ ] 不报 API Key 错误

---

### T-Ollama-02: 基础对话

```
用 Ollama 连接，问：Python 的 GIL 是什么？对多线程有什么影响？
```

**预期结果**：
- 正常返回中文回答
- 响应速度取决于本地硬件

**验证标准**：
- [ ] 收到有意义的回答（非错误信息）
- [ ] 回答涉及 GIL 和多线程的关系
- [ ] 无 API Key / 认证错误

---

### T-Ollama-03: 工具调用

```
用 Ollama 连接（确保模型支持 tool calling，如 qwen2.5:14b+），执行：
在当前目录创建 hello_ollama.txt，内容为 "Hello from Ollama!"。
```

**预期结果**：
- Agent 调用 `file` 工具写入文件
- 文件创建成功

**验证标准**：
- [ ] `hello_ollama.txt` 文件存在
- [ ] 内容为 "Hello from Ollama!"
- [ ] 日志中可见 tool_calls 解析成功

---

### T-Ollama-04: 远程 Ollama 连接

```
使用 --ollama-host <远程IP> 连接远程 Ollama 服务，然后问：你现在连接到哪里？
```

**预期结果**：
- 成功连接远程 Ollama
- 回答中提到远程地址或模型信息

**验证标准**：
- [ ] 连接成功（非超时/拒绝连接）
- [ ] 能正常对话
- [ ] 日志中 base_url 显示远程地址

---

### T-Ollama-05: 流式输出

```
用 Ollama 连接，让 Agent 写一首关于编程的短诗。
```

**预期结果**：
- 使用 `stream_chat` 流式输出
- 文本逐 token 显示（而非一次性输出）

**验证标准**：
- [ ] 文本是逐步显示的（肉眼可感知）
- [ ] 最终内容完整
- [ ] 无截断或乱码

---

### T-Ollama-06: 模型不存在错误处理

```
用 --model nonexistent-model:latest 连接，然后随便说一句话。
```

**预期结果**：
- 清晰的错误提示
- 包含可用模型列表建议

**验证标准**：
- [ ] 错误信息明确（不是通用 500 错误）
- [ ] 提到模型不存在
- [ ] 建议了可用模型

---

### T-Ollama-07: CLI 参数覆盖

```
通过 CLI 指定 Ollama 参数启动：
uv run python -m myagent --provider ollama --model qwen2.5:7b --ollama-host localhost --ollama-port 11434
然后执行：显示 /info
```

**预期结果**：
- `/info` 命令显示 provider=ollama, model=qwen2.5:7b, host=localhost:11434

**验证标准**：
- [ ] Provider 显示为 "ollama"
- [ ] Model 显示为 "qwen2.5:7b"
- [ ] 连接地址正确

---

## 第七部分：实现检查清单

### 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| **新增** | `src/myagent/providers/ollama.py` | Ollama Provider（核心） |
| **修改** | `src/myagent/providers/registry.py` | 注册 OllamaProvider |
| **修改** | `src/myagent/providers/__init__.py` | 导出 OllamaProvider |
| **修改** | `src/myagent/core/config.py` | 增加 ollama_host/port/timeout |
| **修改** | `src/myagent/core/models.py` | ProviderConfig 增加 timeout |
| **修改** | `src/myagent/__main__.py` | 增加 --ollama-host/port CLI 参数 |

### 功能检查清单

- [ ] `OllamaProvider` 继承 `OpenAICompatProvider`，设置 3 个类常量
- [ ] `api_key` 默认值为 `"ollama"`，非必填
- [ ] 支持 `--ollama-host` 和 `--ollama-port` CLI 参数
- [ ] 支持 `config.yaml` 中配置 `ollama_host` / `ollama_port`
- [ ] `base_url` 自动拼接为 `http://{host}:{port}/v1`
- [ ] `check_connection()` 检测 Ollama 可达性
- [ ] `list_models()` 列出可用模型
- [ ] 连接失败时给出明确错误信息和排查建议
- [ ] 模型不存在时提示可用模型列表
- [ ] 不支持 tool calling 的模型有降级策略
- [ ] timeout 默认 120s，可配置
- [ ] SSL 验证可配置（`ollama_ssl_verify`）
- [ ] 流式输出正常工作
- [ ] token 统计正常工作
- [ ] 无 API Key 检查（Ollama 不需要）
- [ ] 启动时可选打印连接状态和模型列表

### 不需要改动

- `src/myagent/providers/openai_compat.py` — 无需修改（Ollama 完全兼容）
- `src/myagent/providers/base.py` — 无需修改
- `src/myagent/engine/react.py` — 无需修改（通过 registry 自动适配）
- `src/myagent/tools/` — 无需修改
- `src/myagent/memory/` — 无需修改
- `src/myagent/ui/` — 无需修改

---

## 第八部分：实现顺序建议

```
Step 1: 新增 ollama.py（继承 OpenAICompatProvider，~80 行）
Step 2: 修改 registry.py + __init__.py（注册 + 导出，~5 行）
Step 3: 修改 models.py（ProviderConfig 加 timeout，~1 行）
Step 4: 修改 config.py（加 ollama 配置项，~3 行）
Step 5: 修改 __main__.py（CLI 参数 + Ollama 初始化逻辑，~30 行）
Step 6: 本地测试（ollama serve → uv run python -m myagent --provider ollama）
Step 7: 执行 T-Ollama-01 ~ T-Ollama-07 测试
```

**总改动量估计：~120 行新增 + ~40 行修改，涉及 6 个文件。**

---

## 第九部分：参考资料

- Ollama 官方文档：https://github.com/ollama/ollama/blob/main/docs/openai.md
- Ollama API 参考：https://github.com/ollama/ollama/blob/main/docs/api.md
- OpenAI Python SDK：https://github.com/openai/openai-python
- 现有 Provider 架构：`src/myagent/providers/openai_compat.py`
