"""终端 UI — 使用 Rich 渲染输出 + Prompt Toolkit 处理输入."""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import TYPE_CHECKING, Callable, Coroutine

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

if TYPE_CHECKING:
    from myagent.engine.react import ReActEngine

logger = logging.getLogger(__name__)

# 命令前缀
COMMAND_PREFIX = "/"


class TerminalUI:
    """终端交互界面.

    负责用户输入处理和富文本输出渲染。
    """

    def __init__(self, engine: ReActEngine, history_file: str | None = None) -> None:
        self.engine = engine
        self.console = Console()
        self._running = False

        # Prompt Toolkit 会话
        history_path = history_file or str(engine.config.memory_dir.parent / "history.txt")
        self.prompt_session: PromptSession[str] = PromptSession(
            history=FileHistory(history_path),
            enable_history_search=True,
        )

    # ── 公开 API ────────────────────────────────────────────

    async def start(self) -> None:
        """启动交互式会话."""
        self._running = True
        self._print_banner()

        while self._running:
            try:
                user_input = await self._get_input()
                if user_input is None:
                    continue

                # 处理命令
                if user_input.startswith(COMMAND_PREFIX):
                    await self._handle_command(user_input)
                    continue

                # 空输入
                if not user_input.strip():
                    continue

                # 执行 ReAct 循环
                await self._process_input(user_input)

            except KeyboardInterrupt:
                self._print_info("\n[Ctrl+C] 使用 /quit 退出")
            except EOFError:
                break
            except Exception as e:
                self._print_error(f"Unexpected error: {e}")
                logger.exception("Unexpected error in UI loop")

        self._print_info("再见！")

    # ── 输入处理 ────────────────────────────────────────────

    async def _get_input(self) -> str | None:
        """获取用户输入."""
        try:
            return await asyncio.to_thread(
                self.prompt_session.prompt,
                "❯ ",
            )
        except (KeyboardInterrupt, EOFError):
            return None

    async def _handle_command(self, command: str) -> None:
        """处理斜杠命令."""
        cmd = command.strip().lower()
        cmd_name = cmd[1:].split()[0] if cmd[1:] else ""
        cmd_args = command.strip()[len(COMMAND_PREFIX) + len(cmd_name) :].strip()

        handlers: dict[str, Callable[..., Coroutine[Any, Any, None]]] = {
            "quit": self._cmd_quit,
            "exit": self._cmd_quit,
            "help": self._cmd_help,
            "clear": self._cmd_clear,
            "info": self._cmd_info,
            "tools": self._cmd_tools,
            "memory": self._cmd_memory,
            "sessions": self._cmd_sessions,
            "history": self._cmd_history,
        }

        handler = handlers.get(cmd_name)
        if handler:
            await handler(cmd_args)
        else:
            self._print_error(f"未知命令: {cmd_name}。输入 /help 查看帮助。")

    async def _process_input(self, user_input: str) -> None:
        """处理用户输入（执行 ReAct 循环）."""
        # 显示用户消息
        self.console.print()
        self.console.print(
            Panel(
                Text(user_input, style="bold cyan"),
                title="You",
                border_style="cyan",
                padding=(0, 1),
            )
        )

        # 执行 ReAct 循环
        try:
            response = await self.engine.run(user_input)

            # 显示助手响应（Markdown 渲染）
            self.console.print()
            self.console.print(
                Panel(
                    Markdown(response),
                    title="MyAgent",
                    border_style="green",
                    padding=(0, 1),
                )
            )
        except Exception as e:
            self._print_error(f"Engine error: {e}")
            logger.exception("Engine error")

    # ── 命令实现 ────────────────────────────────────────────

    async def _cmd_quit(self, _args: str) -> None:
        """退出."""
        self._running = False

    async def _cmd_help(self, _args: str) -> None:
        """显示帮助."""
        help_text = """
**可用命令：**

| 命令 | 说明 |
|------|------|
| /help | 显示此帮助信息 |
| /quit | 退出 MyAgent |
| /clear | 清空当前会话历史 |
| /info | 显示当前会话和配置信息 |
| /tools | 列出所有可用工具 |
| /memory | 显示当前记忆状态 |
| /sessions | 列出所有会话 |
| /history | 显示当前会话对话历史 |

**使用提示：**
- 直接输入文本即可与 MyAgent 对话
- MyAgent 会自动识别你的意图（研究/实施/修复/调查等）
- 支持文件操作、命令执行、代码搜索等工具
- 按 Ctrl+C 中断当前操作
"""
        self.console.print(Markdown(help_text))

    async def _cmd_clear(self, _args: str) -> None:
        """清空会话历史."""
        self.engine.session.clear_history()
        self._print_info("会话历史已清空。")

    async def _cmd_info(self, _args: str) -> None:
        """显示会话信息."""
        info = self.engine.session.info
        provider = self.engine.provider
        text = f"""
**会话 ID**: {info.session_id}
**工作目录**: {info.working_directory}
**消息数量**: {info.message_count}
**Provider**: {provider.provider_id}/{provider.model_id}
**Token 使用**: {provider.get_usage()}
"""
        self.console.print(Markdown(text))

    async def _cmd_tools(self, _args: str) -> None:
        """列出所有工具."""
        tools = self.engine.tool_registry.get_all()
        if not tools:
            self._print_info("无可用工具。")
            return

        lines = [
            f"**{name}** (risk={t.risk_level.value}): {t.description}" for name, t in tools.items()
        ]
        self.console.print(Markdown("\n".join(lines)))

    async def _cmd_memory(self, _args: str) -> None:
        """显示记忆状态."""
        todos = self.engine.memory.working.get_todos()
        todo_text = (
            "\n".join(
                f"- [{'x' if t.status.value == 'completed' else ' '}] {t.content}" for t in todos
            )
            or "(无任务)"
        )

        memory_files = self.engine.memory.longterm._files
        file_text = (
            "\n".join(f"- {name}: {len(content)} chars" for name, content in memory_files.items())
            if memory_files
            else "(无记忆文件)"
        )

        text = f"""## 任务列表
{todo_text}

## 记忆文件
{file_text}"""
        self.console.print(Markdown(text))

    async def _cmd_sessions(self, _args: str) -> None:
        """列出所有会话."""
        sessions = self.engine.session.list_sessions()
        if not sessions:
            self._print_info("无历史会话。")
            return

        lines = [
            f"- **{s.session_id}** ({s.message_count} msgs, {s.updated_at})" for s in sessions[:20]
        ]
        self.console.print(Markdown("**历史会话：**\n" + "\n".join(lines)))

    async def _cmd_history(self, _args: str) -> None:
        """显示当前对话历史."""
        messages = self.engine.session.get_messages()
        if not messages:
            self._print_info("当前会话无历史消息。")
            return

        for msg in messages[-20:]:  # 最近 20 条
            role_style = {
                "system": "dim",
                "user": "cyan",
                "assistant": "green",
                "tool": "yellow",
            }.get(msg.role.value, "white")
            prefix = {
                "system": "[SYS]",
                "user": "[You]",
                "assistant": "[Bot]",
                "tool": "[Tool]",
            }.get(msg.role.value, "[?]")
            content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
            self.console.print(Text(f"{prefix} {content}", style=role_style))

    # ── 辅助方法 ────────────────────────────────────────────

    def _print_banner(self) -> None:
        """打印启动横幅."""
        banner = """
[bold green]MyAgent[/bold green] v0.1.0 — 高效的终端 AI 编程助手

输入文本开始对话，输入 [bold]/help[/bold] 查看命令列表。
"""
        self.console.print(banner)

    def _print_info(self, message: str) -> None:
        """打印信息消息."""
        self.console.print(f"[dim]{message}[/dim]")

    def _print_error(self, message: str) -> None:
        """打印错误消息."""
        self.console.print(f"[bold red]{message}[/bold red]")


__all__ = ["TerminalUI"]
