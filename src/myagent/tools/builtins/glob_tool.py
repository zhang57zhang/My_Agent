"""文件名模式搜索工具 — 使用 pathlib.glob 搜索文件."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from myagent.core.models import RiskLevel, ToolDefinition, ToolParameter, ToolResult
from myagent.tools.base import Tool, ToolContext, get_registry

logger = logging.getLogger(__name__)

MAX_RESULTS = 100


class GlobTool:
    """文件名模式搜索工具."""

    name = "glob"
    description = (
        "按文件名模式搜索文件。支持 glob 模式（如 **/*.py, src/**/*.ts）。"
        "返回匹配的文件路径列表，按修改时间排序，最多返回 100 个结果。"
    )
    risk_level = RiskLevel.LOW
    require_confirmation = False

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="pattern",
                    type="string",
                    description="Glob 搜索模式（如 **/*.py, src/**/*.ts）",
                    required=True,
                ),
                ToolParameter(
                    name="path",
                    type="string",
                    description="搜索根目录（可选，默认当前目录）",
                    required=False,
                ),
            ],
        )

    async def execute(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        pattern = args.get("pattern", "")
        search_path = args.get("path", "") or context.working_directory

        if not pattern:
            return ToolResult(
                tool_call_id="", content="Error: 'pattern' is required", is_error=True
            )

        try:
            base = Path(search_path)
            if not base.is_dir():
                return ToolResult(
                    tool_call_id="",
                    content=f"Error: path is not a directory: {search_path}",
                    is_error=True,
                )

            matches: list[Path] = []
            for p in base.glob(pattern):
                if p.is_file():
                    matches.append(p)
                if len(matches) >= MAX_RESULTS:
                    break

            if not matches:
                return ToolResult(tool_call_id="", content=f"No files found matching '{pattern}'")

            # 按修改时间排序（最新优先）
            matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            result_lines = [str(m) for m in matches]
            return ToolResult(
                tool_call_id="",
                content=f"Found {len(matches)} file(s):\n" + "\n".join(result_lines),
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                content=f"Error searching files: {e}",
                is_error=True,
            )


def _register() -> None:
    get_registry().register(GlobTool())


_register()
