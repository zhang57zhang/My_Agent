"""工具系统核心 — Tool Protocol、ToolRegistry、ToolContext."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from myagent.core.models import RiskLevel, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


# ── Tool Execution Context ────────────────────────────────────


@dataclass
class ToolContext:
    """工具执行上下文，传递给每个工具的 execute 方法.

    Attributes:
        session_id: 当前会话 ID.
        working_directory: 当前工作目录.
        abort_signal: 中止信号，工具应定期检查.
        config: 全局配置引用.
    """

    session_id: str = ""
    working_directory: str = "."
    abort_signal: Any = None  # threading.Event
    config: Any = None  # MyAgentConfig


# ── Tool Protocol ─────────────────────────────────────────────


@runtime_checkable
class Tool(Protocol):
    """工具抽象接口.

    所有工具必须实现此 Protocol。工具通过 ToolRegistry 注册后，
    可被 ReAct 引擎发现和调用。
    """

    @property
    def name(self) -> str:
        """工具唯一标识（用于 function calling 的 function.name）."""
        ...

    @property
    def description(self) -> str:
        """工具描述（LLM 据此决定何时使用此工具）."""
        ...

    @property
    def risk_level(self) -> RiskLevel:
        """工具的风险等级."""
        ...

    @property
    def require_confirmation(self) -> bool:
        """执行前是否需要用户确认."""
        ...

    def get_definition(self) -> ToolDefinition:
        """返回工具定义（用于构建 LLM function calling schema）."""
        ...

    async def execute(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        """执行工具操作.

        Args:
            args: LLM 传入的参数（已解析为 dict）.
            context: 执行上下文.

        Returns:
            ToolResult 包含执行结果或错误信息.
        """
        ...


# ── Tool Registry ─────────────────────────────────────────────


class ToolRegistry:
    """工具注册表（单例模式）.

    管理所有已注册工具的生命周期，提供查询接口。
    """

    _instance: ToolRegistry | None = None

    def __new__(cls) -> ToolRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools: dict[str, Tool] = {}
        return cls._instance

    def register(self, tool: Tool) -> None:
        """注册一个工具实例."""
        if tool.name in self._tools:
            logger.warning(f"Tool '{tool.name}' already registered, replacing.")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} (risk={tool.risk_level.value})")

    def get(self, name: str) -> Tool | None:
        """按名称获取工具."""
        return self._tools.get(name)

    def get_all(self) -> dict[str, Tool]:
        """获取所有已注册工具."""
        return dict(self._tools)

    def get_definitions(self) -> list[ToolDefinition]:
        """获取所有工具的 ToolDefinition 列表."""
        return [tool.get_definition() for tool in self._tools.values()]

    def get_definitions_for_llm(self) -> list[dict[str, Any]]:
        """获取所有工具定义，格式化为 LLM function calling schema.

        Returns:
            OpenAI function calling 格式的 tools 列表.
        """
        result: list[dict[str, Any]] = []
        for tool in self._tools.values():
            definition = tool.get_definition()
            properties: dict[str, Any] = {}
            required: list[str] = []
            for p in definition.parameters:
                prop: dict[str, Any] = {"type": p.type, "description": p.description}
                if p.default is not None:
                    prop["default"] = p.default
                if p.enum:
                    prop["enum"] = p.enum
                properties[p.name] = prop
                if p.required:
                    required.append(p.name)

            result.append(
                {
                    "type": "function",
                    "function": {
                        "name": definition.name,
                        "description": definition.description,
                        "parameters": {
                            "type": "object",
                            "properties": properties,
                            "required": required,
                        },
                    },
                }
            )
        return result

    def clear(self) -> None:
        """清空所有注册的工具（主要用于测试）."""
        self._tools.clear()

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


def get_registry() -> ToolRegistry:
    """获取全局 ToolRegistry 单例."""
    return ToolRegistry()


__all__ = ["Tool", "ToolContext", "ToolRegistry", "get_registry"]
