"""MemoryManager coordinates all 3 memory layers into a coherent API.

- Layer 1: ConversationMemory
- Layer 2: WorkingMemory
- Layer 3: LongTermMemory
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from myagent.core.config import MyAgentConfig
from myagent.core.models import Message
from myagent.memory.base import MemoryEntry
from myagent.memory.conversation import ConversationMemory
from myagent.memory.working import WorkingMemory
from myagent.memory.longterm import LongTermMemory


class MemoryManager:
    """Public API to access all memory layers cohesively."""

    def __init__(self, config: MyAgentConfig) -> None:
        self.config = config
        self.conversation = ConversationMemory()
        self.working = WorkingMemory()
        # Ensure memory_dir exists from config
        memory_dir = Path(config.memory_dir)
        memory_dir.mkdir(parents=True, exist_ok=True)
        self.longterm = LongTermMemory(memory_dir=memory_dir, max_tokens=config.max_memory_tokens)

    # Core API
    def add_message(self, message: Message) -> None:
        self.conversation.add_message(message)

    async def get_context_for_prompt(self) -> str:
        # Gather 3 layers into a single prompt context
        convo_ctx = await self.conversation.to_prompt_context()
        work_ctx = await self.working.to_prompt_context()
        lt_ctx = self.longterm.load_context()
        parts = ["[Conversation]", convo_ctx, "[Working]", work_ctx, "[LongTerm]", lt_ctx]
        return "\n---\n".join([p for p in parts if p.strip() != ""])

    async def search(self, query: str) -> List[MemoryEntry]:  # pragma: no cover
        entries: List[MemoryEntry] = []
        # Search long-term first
        entries.extend(self.longterm.search(query))
        # Search conversation and working memories (simple keyword checks)
        convo_matches = await self.conversation.search(query)
        entries.extend(convo_matches)
        work_matches = await self.working.search(query)
        entries.extend(work_matches)
        return entries

    async def save_all(self) -> None:
        # Persist long-term memory state
        self.longterm.compress_if_needed()
        # Nothing to persist for conversation/working in this simple implementation

    def __repr__(self) -> str:  # pragma: no cover
        return f"MemoryManager(layers=3, longterm={self.longterm})"


__all__ = ["MemoryManager"]
