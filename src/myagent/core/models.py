"""核心数据模型与类型定义."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """消息角色."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class RiskLevel(str, Enum):
    """操作风险等级."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IntentType(str, Enum):
    """用户意图类型."""

    RESEARCH = "research"  # 研究/理解
    IMPLEMENT = "implement"  # 实施（显式）
    INVESTIGATE = "investigate"  # 调查
    EVALUATE = "evaluate"  # 评估
    FIX = "fix"  # 修复
    REFACTOR = "refactor"  # 重构
    AMBIGUOUS = "ambiguous"  # 不明确


class TodoStatus(str, Enum):
    """任务状态."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TodoPriority(str, Enum):
    """任务优先级."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ── Message Models ──────────────────────────────────────────────


class Message(BaseModel):
    """对话消息."""

    role: MessageRole
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class ToolCall(BaseModel):
    """工具调用请求."""

    id: str
    function: str
    arguments: dict[str, Any]


class ToolResult(BaseModel):
    """工具调用结果."""

    tool_call_id: str
    content: str
    is_error: bool = False


# ── Task Models ────────────────────────────────────────────────


class TodoItem(BaseModel):
    """任务项."""

    content: str
    status: TodoStatus = TodoStatus.PENDING
    priority: TodoPriority = TodoPriority.MEDIUM


# ── Tool Models ────────────────────────────────────────────────


class ToolParameter(BaseModel):
    """工具参数定义."""

    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum: list[str] | None = None


class ToolDefinition(BaseModel):
    """工具定义（用于 LLM function calling）."""

    name: str
    description: str
    parameters: list[ToolParameter] = Field(default_factory=list)


class ToolPermission(BaseModel):
    """工具权限配置."""

    risk_level: RiskLevel = RiskLevel.LOW
    require_confirmation: bool = False
    allowed_patterns: list[str] | None = None
    denied_patterns: list[str] | None = None


# ── Session Models ─────────────────────────────────────────────


class SessionInfo(BaseModel):
    """会话信息."""

    session_id: str
    created_at: str
    updated_at: str
    message_count: int = 0
    working_directory: str = ""


# ── Provider Models ────────────────────────────────────────────


class ProviderConfig(BaseModel):
    """LLM Provider 配置."""

    provider_id: str  # e.g. "zhipu", "qwen", "ollama"
    model_id: str  # e.g. "glm-4-plus", "qwen2.5"
    api_key: str
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.9
    timeout: float | None = None


class LLMResponse(BaseModel):
    """LLM 响应."""

    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    finish_reason: str | None = None
    usage: dict[str, int] | None = None
