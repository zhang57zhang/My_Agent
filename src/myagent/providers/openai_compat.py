"""OpenAI 兼容适配器 — 智谱/通义等国产模型的共享基类.

国产 LLM 提供商大多兼容 OpenAI API 格式，因此将通用逻辑抽取到此基类中。
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from openai import AsyncOpenAI

from myagent.core.models import (
    LLMResponse,
    Message,
    MessageRole,
    ToolCall,
    ToolDefinition,
    ToolParameter,
)
from myagent.providers.base import (
    AuthenticationError,
    ContextLengthExceeded,
    ProviderError,
    RateLimitError,
)

logger = logging.getLogger(__name__)


class OpenAICompatProvider:
    """OpenAI 兼容 API 适配器基类.

    子类只需设置 class-level 默认值即可使用：
    - PROVIDER_ID: str
    - DEFAULT_MODEL: str
    - DEFAULT_BASE_URL: str
    """

    PROVIDER_ID: str = "openai-compat"
    DEFAULT_MODEL: str = "gpt-4"
    DEFAULT_BASE_URL: str = "https://api.openai.com/v1"

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str,
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 0.9,
    ) -> None:
        self._model = model or self.DEFAULT_MODEL
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._top_p = top_p
        self._usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or self.DEFAULT_BASE_URL,
        )

    @property
    def provider_id(self) -> str:
        return self.PROVIDER_ID

    @property
    def model_id(self) -> str:
        return self._model

    def get_usage(self) -> dict[str, int]:
        return dict(self._usage)

    # ── 内部方法 ────────────────────────────────────────────

    def _build_messages(self, messages: list[Message]) -> list[dict[str, str]]:
        """将 Message 模型转换为 OpenAI 格式."""
        result: list[dict[str, str]] = []
        for msg in messages:
            result.append({"role": msg.role.value, "content": msg.content})
        return result

    def _build_tools(self, functions: list[ToolDefinition] | None) -> list[dict[str, Any]] | None:
        """将 ToolDefinition 转换为 OpenAI function calling 格式."""
        if not functions:
            return None

        tools: list[dict[str, Any]] = []
        for func in functions:
            params: dict[str, Any] = {
                "type": "object",
                "properties": {},
                "required": [],
            }
            for p in func.parameters:
                prop: dict[str, Any] = {"type": p.type, "description": p.description}
                if p.default is not None:
                    prop["default"] = p.default
                if p.enum:
                    prop["enum"] = p.enum
                params["properties"][p.name] = prop
                if p.required:
                    params["required"].append(p.name)

            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": func.name,
                        "description": func.description,
                        "parameters": params,
                    },
                }
            )
        return tools

    def _parse_tool_calls(self, raw_calls: list[Any] | None) -> list[ToolCall] | None:
        """解析 OpenAI 响应中的 tool_calls."""
        if not raw_calls:
            return None
        result: list[ToolCall] = []
        for call in raw_calls:
            func = call.function
            args = {}
            try:
                args = (
                    json.loads(func.arguments)
                    if isinstance(func.arguments, str)
                    else func.arguments
                )
            except json.JSONDecodeError:
                args = {"raw": func.arguments}
            result.append(
                ToolCall(
                    id=call.id,
                    function=func.name,
                    arguments=args,
                )
            )
        return result

    async def _call_with_retry(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None,
        stream: bool = False,
    ) -> Any:
        """带指数退避重试的 API 调用."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                kwargs: dict[str, Any] = {
                    "model": self._model,
                    "messages": messages,
                    "temperature": self._temperature,
                    "max_tokens": self._max_tokens,
                    "top_p": self._top_p,
                    "stream": stream,
                }
                if tools:
                    kwargs["tools"] = tools
                return await self._client.chat.completions.create(**kwargs)

            except Exception as e:
                error_str = str(e).lower()
                if "rate" in error_str or "429" in error_str:
                    if attempt < max_retries - 1:
                        wait = 2 ** (attempt + 1)
                        logger.warning(f"Rate limited, retrying in {wait}s (attempt {attempt + 1})")
                        await asyncio.sleep(wait)
                        continue
                    raise RateLimitError(
                        f"Rate limit exceeded after {max_retries} retries: {e}",
                        provider_id=self.PROVIDER_ID,
                    ) from e
                elif "context_length" in error_str or "token" in error_str:
                    raise ContextLengthExceeded(
                        f"Context length exceeded: {e}",
                        provider_id=self.PROVIDER_ID,
                    ) from e
                elif "auth" in error_str or "key" in error_str or "401" in error_str:
                    raise AuthenticationError(
                        f"Authentication failed: {e}",
                        provider_id=self.PROVIDER_ID,
                    ) from e
                else:
                    raise ProviderError(
                        f"API call failed: {e}",
                        provider_id=self.PROVIDER_ID,
                    ) from e

    def _update_usage(self, usage: Any) -> None:
        """更新 token 使用统计."""
        if usage:
            self._usage["prompt_tokens"] = getattr(usage, "prompt_tokens", 0) or 0
            self._usage["completion_tokens"] = getattr(usage, "completion_tokens", 0) or 0
            self._usage["total_tokens"] = getattr(usage, "total_tokens", 0) or 0

    # ── 公开方法 ────────────────────────────────────────────

    async def chat(
        self,
        messages: list[Message],
        *,
        functions: list[ToolDefinition] | None = None,
    ) -> LLMResponse:
        """发送聊天请求."""
        api_messages = self._build_messages(messages)
        api_tools = self._build_tools(functions)

        response = await self._call_with_retry(api_messages, api_tools, stream=False)

        choice = response.choices[0]
        content = choice.message.content

        raw_tool_calls = getattr(choice.message, "tool_calls", None)
        tool_calls = self._parse_tool_calls(raw_tool_calls) if raw_tool_calls else None

        self._update_usage(getattr(response, "usage", None))

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason,
            usage=self.get_usage(),
        )

    async def stream_chat(
        self,
        messages: list[Message],
        *,
        functions: list[ToolDefinition] | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式聊天请求."""
        api_messages = self._build_messages(messages)
        api_tools = self._build_tools(functions)

        response = await self._call_with_retry(api_messages, api_tools, stream=True)

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

        # stream 模式下 usage 可能不在最终 chunk 中
        if hasattr(response, "usage") and response.usage:
            self._update_usage(response.usage)
