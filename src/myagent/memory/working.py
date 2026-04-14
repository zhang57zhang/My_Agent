"""Layer 2: Working Memory - tasks, current focus, and session notes.

Stores current task state including a list of TodoItem and current file edits.
Persistence is optional and kept in-memory by default.
"""

from __future__ import annotations

from typing import List, Optional
from datetime import datetime

from myagent.core.models import TodoItem, TodoStatus, TodoPriority
from .base import MemoryStore, MemoryEntry


class WorkingMemory(MemoryStore):
    """Working memory for current session: todos, current files, notes."""

    def __init__(self) -> None:
        self._todos: List[TodoItem] = []
        self._current_files: List[str] = []
        self._session_notes: str = ""

    # Todo management
    async def add(self, key: str, value: TodoItem) -> None:  # type: ignore[override]
        self._todos.append(value)

    async def get(self, key: str) -> TodoItem | None:  # type: ignore[override]
        if not self._todos:
            return None
        return self._todos[-1]

    async def search(self, query: str) -> List[MemoryEntry]:  # pragma: no cover
        results: List[MemoryEntry] = []
        for t in self._todos:
            if query.lower() in t.content.lower():
                results.append(
                    MemoryEntry(
                        source="working memory",
                        content=t.content,
                        metadata={"status": t.status.value},
                    )
                )
        return results

    async def clear(self) -> None:  # pragma: no cover
        self._todos.clear()
        self._current_files.clear()
        self._session_notes = ""

    async def to_prompt_context(self) -> str:
        lines: List[str] = []
        lines.append("## Working Memory: Todos")
        for idx, t in enumerate(self._todos, start=1):
            lines.append(f"{idx}. [{t.status.value}] {t.content} (priority={t.priority.value})")
        lines.append("")
        lines.append("## Current Files")
        for f in self._current_files:
            lines.append(f"- {f}")
        if self._session_notes:
            lines.append("")
            lines.append("## Session Notes")
            lines.append(self._session_notes)
        return "\n".join(lines)

    # API surface
    def add_todo(self, content: str, priority: TodoPriority = TodoPriority.MEDIUM) -> TodoItem:
        item = TodoItem(content=content, status=TodoStatus.PENDING, priority=priority)
        self._todos.append(item)
        # Auto-advance first todo to IN_PROGRESS if none is in_progress
        if (
            not any(t.status == TodoStatus.IN_PROGRESS for t in self._todos)
            and item.status == TodoStatus.PENDING
        ):
            item.status = TodoStatus.IN_PROGRESS
        return item

    def update_todo(
        self,
        index: int,
        *,
        content: str | None = None,
        status: TodoStatus | None = None,
        priority: TodoPriority | None = None,
    ) -> None:
        if 0 <= index < len(self._todos):
            t = self._todos[index]
            if content is not None:
                t.content = content
            if status is not None:
                t.status = status
            if priority is not None:
                t.priority = priority

    def get_todos(self) -> List[TodoItem]:
        return list(self._todos)

    def complete_todo(self, index: int) -> None:
        if 0 <= index < len(self._todos):
            self._todos[index].status = TodoStatus.COMPLETED

    def set_current_files(self, files: List[str]) -> None:
        self._current_files = list(files)

    # Convenience helpers
    def set_session_notes(self, notes: str) -> None:
        self._session_notes = notes

    # Public access to internal state for manager usage (optional)
    def __repr__(self) -> str:  # pragma: no cover
        return f"WorkingMemory(todos={len(self._todos)}, files={len(self._current_files)})"


__all__ = ["WorkingMemory"]
