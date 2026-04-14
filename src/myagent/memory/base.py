"""Memory core abstractions and shared types for MyAgent memory system.

This module defines the MemoryStore Protocol, MemoryEntry data class,
and lightweight type aliases used by all memory layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Optional, Dict, List

from myagent.core.models import Message, TodoItem, TodoStatus, TodoPriority
from myagent.core.config import MyAgentConfig


@dataclass
class MemoryEntry:
    """Represents a piece of memory contributed by any layer.

    Attributes:
        source: Layer name (e.g., "conversation", "working", "longterm").
        content: Textual memory content.
        relevance_score: Relative relevance for prompt injection.
        metadata: Optional extra information for debugging/traceability.
    """

    source: str
    content: str
    relevance_score: float = 0.0
    metadata: Dict[str, Any] | None = None


class MemoryStore(Protocol):
    """Abstract storage for memory layers.

    All concrete stores must implement an asynchronous API to align with
    typical async I/O in agent systems.
    """

    async def add(self, key: str, value: Any) -> None:  # pragma: no cover
        ...

    async def get(self, key: str) -> Any | None:  # pragma: no cover
        ...

    async def search(self, query: str) -> List[MemoryEntry]:  # pragma: no cover
        ...

    async def clear(self) -> None:  # pragma: no cover
        ...

    async def to_prompt_context(self) -> str:  # pragma: no cover
        ...


__all__ = ["MemoryEntry", "MemoryStore"]
