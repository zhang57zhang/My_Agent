"""LLM Provider 抽象接口与自定义异常."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from myagent.core.models import LLMResponse, Message, ToolDefinition

logger = logging.getLogger(__name__)


# ── Custom Exceptions ─────────────────────────────────────────


class ProviderError(Exception):
    """Provider 基础异常."""

    def __init__(self, message: str, provider_id: str = "") -> None:
        self.provider_id = provider_id
        super().__init__(message)


class RateLimitError(ProviderError):
    """速率限制异常."""

    pass


class ContextLengthExceeded(ProviderError):
    """上下文长度超限."""

    pass


class AuthenticationError(ProviderError):
    """认证失败."""

    pass


# ── Provider Protocol ─────────────────────────────────────────


class Provider(Protocol):
    """LLM Provider 抽象接口.

    所有 provider 必须实现此 Protocol。使用 Protocol 而非 ABC，
    支持结构化子类型（鸭子类型 + 静态检查）。
    """

    @property
    def provider_id(self) -> str:
        """Provider 唯一标识 (e.g. 'zhipu', 'qwen')."""
        ...

    @property
    def model_id(self) -> str:
        """当前使用的模型 ID."""
        ...

    async def chat(
        self,
        messages: list[Message],
        *,
        functions: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """发送聊天请求并获取完整响应.

        Args:
            messages: 对话消息列表.
            functions: 可用的工具定义列表（用于 function calling）.

        Returns:
            LLMResponse 包含 content、tool_calls、usage 等.
        """
        ...

    async def stream_chat(
        self,
        messages: list[Message],
        *,
        functions: list[ToolDefinition] | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式聊天请求，逐 token 产出文本.

        Args:
            messages: 对话消息列表.
            functions: 可用的工具定义列表.

        Yields:
            文本片段字符串.
        """
        ...

    def get_usage(self) -> dict[str, int]:
        """获取 token 使用统计.

        Returns:
            {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
        """
        ...


__all__ = [
    "Provider",
    "ProviderError",
    "RateLimitError",
    "ContextLengthExceeded",
    "AuthenticationError",
]
