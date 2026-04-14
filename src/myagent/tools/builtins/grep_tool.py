"""文件内容搜索工具 — 使用正则表达式搜索文件内容."""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any

from myagent.core.models import RiskLevel, ToolDefinition, ToolParameter, ToolResult
from myagent.tools.base import Tool, ToolContext, get_registry

logger = logging.getLogger(__name__)

MAX_SEARCH_TIME = 60  # 秒
MAX_OUTPUT_SIZE = 256 * 1024  # 256KB
MAX_RESULTS_PER_FILE = 50
MAX_TOTAL_RESULTS = 200


class GrepTool:
    """文件内容搜索工具."""

    name = "grep"
    description = (
        "按正则表达式搜索文件内容。返回匹配的文件路径、行号和匹配内容。"
        "支持 include 参数过滤文件类型（如 '*.py'）。"
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
                    description="正则表达式搜索模式",
                    required=True,
                ),
                ToolParameter(
                    name="path",
                    type="string",
                    description="搜索根目录（可选，默认当前目录）",
                    required=False,
                ),
                ToolParameter(
                    name="include",
                    type="string",
                    description="文件过滤模式（如 '*.py', '*.ts'，可选）",
                    required=False,
                ),
            ],
        )

    async def execute(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        pattern = args.get("pattern", "")
        search_path = args.get("path", "") or context.working_directory
        include = args.get("include", "")

        if not pattern:
            return ToolResult(
                tool_call_id="", content="Error: 'pattern' is required", is_error=True
            )

        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return ToolResult(
                tool_call_id="",
                content=f"Error: invalid regex pattern: {e}",
                is_error=True,
            )

        try:
            base = Path(search_path)
            if not base.is_dir():
                return ToolResult(
                    tool_call_id="",
                    content=f"Error: path is not a directory: {search_path}",
                    is_error=True,
                )

            results: list[str] = []
            total_output = 0
            total_results = 0
            start_time = time.time()

            for filepath in base.rglob("*"):
                # 超时检查
                if time.time() - start_time > MAX_SEARCH_TIME:
                    results.append(f"\n[Search timed out after {MAX_SEARCH_TIME}s]")
                    break

                if not filepath.is_file():
                    continue
                if include and not filepath.match(include):
                    continue

                # 跳过二进制文件和大文件
                try:
                    if filepath.stat().st_size > 1024 * 1024:  # > 1MB
                        continue
                except OSError:
                    continue

                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                match_line = f"{filepath}:{line_num}: {line.rstrip()}"
                                results.append(match_line)
                                total_output += len(match_line)
                                total_results += 1

                                if total_output > MAX_OUTPUT_SIZE:
                                    results.append(
                                        f"\n[Output truncated at {MAX_OUTPUT_SIZE // 1024}KB]"
                                    )
                                    break
                                if total_results >= MAX_TOTAL_RESULTS:
                                    results.append(f"\n[Reached max {MAX_TOTAL_RESULTS} results]")
                                    break
                        else:
                            continue
                        break  # 内层 break 跳出外层
                except (OSError, UnicodeDecodeError):
                    continue

            if not results:
                return ToolResult(
                    tool_call_id="",
                    content=f"No matches found for pattern '{pattern}'",
                )

            return ToolResult(
                tool_call_id="",
                content="\n".join(results),
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                content=f"Error searching content: {e}",
                is_error=True,
            )


def _register() -> None:
    get_registry().register(GrepTool())


_register()
