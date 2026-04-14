"""Layer 1: Conversation Memory - in-memory session history.

Stores full conversation history as a list of Message objects.
No persistence beyond the session.
"""

from __future__ import annotations

from typing import List
from myagent.core.models import Message

from .base import MemoryStore, MemoryEntry


class ConversationMemory(MemoryStore):
    """In-memory conversation memory for the current session."""

    def __init__(self) -> None:
        self._history: List[Message] = []

    # MemoryStore interface (async by convention; implement as async-safe wrappers)
    async def add(self, key: str, value: Message) -> None:  # type: ignore[override]
        # key is ignored for in-memory simple store; we only append
        self._history.append(value)

    async def get(self, key: str) -> Message | None:  # type: ignore[override]
        # Not a key-value store; provide last message for compatibility
        if not self._history:
            return None
        return self._history[-1]

    async def search(self, query: str) -> List[MemoryEntry]:  # pragma: no cover
        results: List[MemoryEntry] = []
        for m in self._history:
            if query.lower() in m.content.lower():
                results.append(
                    MemoryEntry(
                        source="conversation history", content=m.content, metadata={"role": m.role}
                    )
                )
        return results

    async def clear(self) -> None:  # pragma: no cover
        self._history.clear()

    async def to_prompt_context(self) -> str:
        # Render as a simple dialogue transcript preserving order
        lines: List[str] = []
        for m in self._history:
            role = getattr(m, "role", None)
            role_str = getattr(role, "value", str(role)) if role is not None else "user"
            content = m.content
            lines.append(f"{role_str}: {content}")
        return "\n".join(lines)

    # Convenience helpers
    def add_message(self, message: Message) -> None:
        self._history.append(message)

    def get_history(self) -> List[Message]:
        return list(self._history)

    def get_recent(self, n: int) -> List[Message]:
        return list(self._history[-n:]) if n > 0 else []

    # Backward compatibility name expected by interface
    async def __aenter__(self):  # pragma: no cover
        return self

    async def __aexit__(self, exc_type, exc, tb):  # pragma: no cover
        await self.clear()


__all__ = ["ConversationMemory"]
