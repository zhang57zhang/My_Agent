"""Shell 命令执行工具 — 带超时、风险检测和目录控制."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

from myagent.core.models import RiskLevel, ToolDefinition, ToolParameter, ToolResult
from myagent.tools.base import Tool, ToolContext, get_registry

logger = logging.getLogger(__name__)

# 危险命令模式（同时匹配子串和完整命令）
DANGEROUS_PATTERNS = [
    "rm -rf /",
    "rm -rf /*",
    "rm -rf .",
    "rm -rf *",
    "mkfs",
    "dd if=",
    "> /dev/sd",
    "shutdown",
    "reboot",
    "halt",
    "format ",
    "del /f /s /q C:",
]

# 危险命令前缀（匹配命令开头部分）
DANGEROUS_PREFIXES = [
    "rm -rf",
    "rmdir /s",
    "del /f /s /q",
    "format",
    "diskpart",
    "net user",
    "net localgroup administrators",
]

DEFAULT_TIMEOUT = 120  # 秒


class BashTool:
    """Shell 命令执行工具."""

    name = "bash"
    description = (
        "执行 Shell 命令。用于构建、测试、Git 操作、包管理等。"
        "不要用此工具做文件读写（应使用 file 工具）。"
    )
    risk_level = RiskLevel.MEDIUM
    require_confirmation = True

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="command",
                    type="string",
                    description="要执行的 Shell 命令",
                    required=True,
                ),
                ToolParameter(
                    name="timeout",
                    type="integer",
                    description="超时时间（秒），默认 120",
                    required=False,
                    default=DEFAULT_TIMEOUT,
                ),
                ToolParameter(
                    name="workdir",
                    type="string",
                    description="工作目录（可选）",
                    required=False,
                ),
            ],
        )

    async def execute(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        command = args.get("command", "")
        timeout = int(args.get("timeout", DEFAULT_TIMEOUT))
        workdir = args.get("workdir", "") or context.working_directory

        if not command:
            return ToolResult(
                tool_call_id="", content="Error: 'command' is required", is_error=True
            )

        # 风险检测
        risk = self._assess_risk(command)
        if risk == "high":
            return ToolResult(
                tool_call_id="",
                content=f"Error: dangerous command detected and blocked: {command}",
                is_error=True,
            )

        # 验证工作目录
        if workdir:
            try:
                wd = Path(workdir)
                if not wd.is_dir():
                    return ToolResult(
                        tool_call_id="",
                        content=f"Error: working directory does not exist: {workdir}",
                        is_error=True,
                    )
            except Exception as e:
                return ToolResult(
                    tool_call_id="",
                    content=f"Error: invalid working directory: {e}",
                    is_error=True,
                )

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=workdir or None,
                encoding="utf-8",
                errors="replace",
            )

            output_parts: list[str] = []
            if result.stdout:
                output_parts.append(result.stdout)
            if result.stderr:
                output_parts.append(f"[stderr]\n{result.stderr}")
            if result.returncode != 0:
                output_parts.append(f"[exit code: {result.returncode}]")

            content = "\n".join(output_parts) if output_parts else "(no output)"
            return ToolResult(tool_call_id="", content=content, is_error=result.returncode != 0)

        except subprocess.TimeoutExpired:
            return ToolResult(
                tool_call_id="",
                content=f"Error: command timed out after {timeout}s: {command}",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                content=f"Error executing command: {e}",
                is_error=True,
            )

    def _assess_risk(self, command: str) -> str:
        """评估命令风险等级."""
        cmd_lower = command.lower().strip()
        # 匹配完整危险模式
        for pattern in DANGEROUS_PATTERNS:
            if pattern.lower() in cmd_lower:
                return "high"
        # 匹配危险命令前缀（阻止 rm -rf 后跟任何路径）
        for prefix in DANGEROUS_PREFIXES:
            if cmd_lower.startswith(prefix):
                return "high"
        # 检测递归删除模式
        import re

        if re.search(r"rm\s+(-[rfRF]+\s+|--recurs|del\s+/[fsFSqQ])", cmd_lower):
            return "high"
        return "low"


def _register() -> None:
    get_registry().register(BashTool())


_register()
