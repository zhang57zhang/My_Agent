"""文件操作工具 — read / write / edit / list_directory."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from myagent.core.models import RiskLevel, ToolCall, ToolDefinition, ToolParameter, ToolResult
from myagent.tools.base import Tool, ToolContext, get_registry

logger = logging.getLogger(__name__)

# 安全限制
MAX_FILE_SIZE = 50 * 1024  # 50KB
DEFAULT_LINE_LIMIT = 2000


def _validate_path(path: str) -> Path:
    """验证路径安全性（防止路径遍历）."""
    p = Path(path).resolve()
    parts = p.parts
    if ".." in parts:
        raise ValueError(f"Unsafe path: path traversal detected in '{path}'")
    return p


def _is_binary(filepath: Path) -> bool:
    """检测文件是否为二进制文件."""
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(8192)
            if b"\x00" in chunk:
                return True
        return False
    except OSError:
        return True


class FileTool:
    """文件读写操作工具."""

    name = "file"
    description = (
        "文件操作工具。支持："
        "read（读取文件，支持 offset/limit 分段读取）、"
        "write（写入文件）、"
        "edit（查找替换文本）、"
        "list（列出目录内容）。"
        "通过 action 参数选择操作类型。"
    )
    risk_level = RiskLevel.LOW
    require_confirmation = False

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=[
                ToolParameter(
                    name="action",
                    type="string",
                    description="操作类型: read / write / edit / list",
                    required=True,
                    enum=["read", "write", "edit", "list"],
                ),
                ToolParameter(
                    name="path",
                    type="string",
                    description="文件或目录路径",
                    required=True,
                ),
                ToolParameter(
                    name="content",
                    type="string",
                    description="写入或替换的内容（write/edit 时必需）",
                    required=False,
                ),
                ToolParameter(
                    name="offset",
                    type="integer",
                    description="读取起始行号（从 1 开始，read 时可选）",
                    required=False,
                    default=1,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="最大读取行数（read 时可选）",
                    required=False,
                    default=DEFAULT_LINE_LIMIT,
                ),
                ToolParameter(
                    name="old_text",
                    type="string",
                    description="要被替换的原始文本（edit 时必需）",
                    required=False,
                ),
                ToolParameter(
                    name="new_text",
                    type="string",
                    description="替换后的新文本（edit 时必需）",
                    required=False,
                ),
            ],
        )

    async def execute(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        action = args.get("action", "")
        path = args.get("path", "")

        if not path:
            return ToolResult(tool_call_id="", content="Error: 'path' is required", is_error=True)

        try:
            validated = _validate_path(path)
        except ValueError as e:
            return ToolResult(tool_call_id="", content=f"Error: {e}", is_error=True)

        handler = {
            "read": self._read,
            "write": self._write,
            "edit": self._edit,
            "list": self._list_dir,
        }.get(action)

        if handler is None:
            return ToolResult(
                tool_call_id="",
                content=f"Error: unknown action '{action}'. Use: read/write/edit/list",
                is_error=True,
            )

        return handler(validated, args)

    def _read(self, filepath: Path, args: dict[str, Any]) -> ToolResult:
        """读取文件内容."""
        if not filepath.exists():
            return ToolResult(
                tool_call_id="",
                content=f"Error: file not found: {filepath}",
                is_error=True,
            )
        if not filepath.is_file():
            return ToolResult(
                tool_call_id="",
                content=f"Error: not a file: {filepath}",
                is_error=True,
            )
        if _is_binary(filepath):
            return ToolResult(
                tool_call_id="",
                content=f"Error: binary file detected: {filepath}",
                is_error=True,
            )

        file_size = filepath.stat().st_size
        if file_size > MAX_FILE_SIZE:
            return ToolResult(
                tool_call_id="",
                content=f"Error: file too large ({file_size} bytes, max {MAX_FILE_SIZE}): {filepath}",
                is_error=True,
            )

        offset = max(1, int(args.get("offset", 1)))
        limit = int(args.get("limit", DEFAULT_LINE_LIMIT))

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total = len(lines)
            start = max(0, offset - 1)
            end = min(total, start + limit)
            selected = lines[start:end]

            numbered = "".join(f"{i + start + 1}: {line}" for i, line in enumerate(selected))
            header = f"[{start + 1}-{end} of {total} lines]"
            return ToolResult(tool_call_id="", content=f"{header}\n{numbered}")
        except OSError as e:
            return ToolResult(tool_call_id="", content=f"Error reading file: {e}", is_error=True)

    def _write(self, filepath: Path, args: dict[str, Any]) -> ToolResult:
        """写入文件."""
        content = args.get("content", "")
        if content is None:
            return ToolResult(
                tool_call_id="",
                content="Error: 'content' is required for write action",
                is_error=True,
            )

        try:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult(
                tool_call_id="",
                content=f"Written {len(content)} characters to {filepath}",
            )
        except OSError as e:
            return ToolResult(tool_call_id="", content=f"Error writing file: {e}", is_error=True)

    def _edit(self, filepath: Path, args: dict[str, Any]) -> ToolResult:
        """查找替换文本."""
        old_text = args.get("old_text") or args.get("content", "")
        new_text = args.get("new_text", "")

        if not old_text:
            return ToolResult(
                tool_call_id="",
                content="Error: 'old_text' is required for edit action",
                is_error=True,
            )
        if not new_text:
            return ToolResult(
                tool_call_id="",
                content="Error: 'new_text' must differ from 'old_text'",
                is_error=True,
            )

        if not filepath.exists():
            return ToolResult(
                tool_call_id="",
                content=f"Error: file not found: {filepath}",
                is_error=True,
            )

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            if old_text not in content:
                return ToolResult(
                    tool_call_id="",
                    content=f"Error: 'old_text' not found in {filepath}",
                    is_error=True,
                )

            occurrences = content.count(old_text)
            if occurrences > 1:
                return ToolResult(
                    tool_call_id="",
                    content=f"Error: found {occurrences} occurrences of old_text. Provide more context to make it unique.",
                    is_error=True,
                )

            new_content = content.replace(old_text, new_text, 1)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)

            return ToolResult(tool_call_id="", content=f"Edited {filepath} (1 replacement)")
        except OSError as e:
            return ToolResult(tool_call_id="", content=f"Error editing file: {e}", is_error=True)

    def _list_dir(self, dirpath: Path, args: dict[str, Any]) -> ToolResult:
        """列出目录内容."""
        if not dirpath.exists():
            return ToolResult(
                tool_call_id="",
                content=f"Error: path not found: {dirpath}",
                is_error=True,
            )
        if not dirpath.is_dir():
            return ToolResult(
                tool_call_id="",
                content=f"Error: not a directory: {dirpath}",
                is_error=True,
            )

        try:
            entries: list[str] = []
            for item in sorted(dirpath.iterdir()):
                suffix = "/" if item.is_dir() else ""
                entries.append(f"{item.name}{suffix}")
            return ToolResult(
                tool_call_id="", content="\n".join(entries) if entries else "(empty directory)"
            )
        except PermissionError as e:
            return ToolResult(
                tool_call_id="", content=f"Error: permission denied: {e}", is_error=True
            )


# 自动注册
def _register() -> None:
    get_registry().register(FileTool())


_register()
