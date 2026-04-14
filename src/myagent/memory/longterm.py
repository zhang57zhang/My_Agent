"""Layer 3: Long-term memory persisted in Markdown files.

Stores persistent knowledge in the memory directory as Markdown files.
Provides loading, saving, searching, and compression to stay within token limits.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict
import re
from datetime import datetime

from myagent.core.config import MyAgentConfig
from myagent.core.models import Message  # For type compatibility in metadata
from .base import MemoryEntry


class LongTermMemory:
    """Persisted memory across sessions using Markdown files."""

    def __init__(self, memory_dir: Path, max_tokens: int = 800) -> None:
        self.memory_dir: Path = memory_dir
        self.max_tokens: int = max_tokens
        self.files: Dict[str, Path] = {
            "MEMORY": self.memory_dir / "MEMORY.md",
            "USER": self.memory_dir / "USER.md",
            "IDENTITY": self.memory_dir / "IDENTITY.md",
            "TOOLS": self.memory_dir / "TOOLS.md",
        }
        self._ensure_files()
        self._loaded: List[str] = []  # track which contents loaded/changed for compression sanity
        self._contents_cache: Dict[str, str] = {}
        self.load_all()

    def _ensure_files(self) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        for name, path in self.files.items():
            if not path.exists():
                path.write_text(self._default_content(name), encoding="utf-8")

    def _default_content(self, name: str) -> str:
        header = f"# Long-term Memory - {name}\n\n"
        sections = {
            "MEMORY": "## User Preferences\n- Prefers Chinese communication\n- Uses Python 3.12\n",
            "USER": "## User Profile\n- Name: Agent\n- Role: Assistant\n",
            "IDENTITY": "## Identity\n- Behavior: helpful, concise, curious\n",
            "TOOLS": "## Tools & Environment\n- OS: Windows\n- Python: 3.12\n",
        }
        return header + sections.get(name, "## Memory\n- Nothing yet\n")

    def load_all(self) -> str:
        """Read all markdown memory files and cache their contents."""
        combined: List[str] = []
        for key, path in self.files.items():
            content = path.read_text(encoding="utf-8")
            self._contents_cache[str(path)] = content
            combined.append(content)
        return "\n".join(combined)

    def save_memory(self, key: str, content: str) -> None:
        path = self.files.get(key, None)
        if not path:
            return
        path.write_text(content, encoding="utf-8")
        self._contents_cache[str(path)] = content

    def compress_if_needed(self) -> None:
        """Very naive compression: if combined token-ish length exceeds max_tokens,
        drop oldest non-critical sections from MEMORY.md until within limit."""
        all_text = "\n".join(self._contents_cache.values())
        tokens = len(all_text.split())
        if tokens <= self.max_tokens:
            return
        # Simple strategy: truncate MEMORY.md content by removing lines older than a threshold
        mem_path = self.files["MEMORY"]
        lines = mem_path.read_text(encoding="utf-8").splitlines()
        # Try removing from the start (oldest sections) while keeping header
        header = lines[0] if lines else ""
        new_lines = [header]
        for line in lines[1:]:
            if len(" ".join(new_lines)) // 2 > self.max_tokens:
                break
            new_lines.append(line)
        mem_path.write_text("\n".join(new_lines), encoding="utf-8")

    # Basic search
    def search(self, query: str) -> List[MemoryEntry]:  # pragma: no cover
        results: List[MemoryEntry] = []
        pattern = re.compile(query, re.IGNORECASE)
        for path in self.files.values():
            text = path.read_text(encoding="utf-8")
            for m in pattern.finditer(text):
                snippet_start = max(0, m.start() - 60)
                snippet = text[snippet_start : m.end() + 60]
                results.append(
                    MemoryEntry(source=str(path.name), content=snippet, relevance_score=1.0)
                )
        return results

    def add_fact(self, content: str, source: str = "MEMORY") -> None:
        path = self.files.get(source, self.files["MEMORY"])
        existing = path.read_text(encoding="utf-8")
        updated = existing.rstrip() + f"\n- {content}\n"
        path.write_text(updated, encoding="utf-8")
        self._contents_cache[str(path)] = updated

    def get_facts(self) -> List[str]:  # pragma: no cover
        facts: List[str] = []
        for path in self.files.values():
            facts.append(path.read_text(encoding="utf-8"))
        return facts

    def load_context_text(self) -> str:  # pragma: no cover
        return self.load_all()

    # Convenience interface for MemoryManager
    def load_context(self) -> str:
        return self.load_all()

    # Public helpers for tests/usage
    def __repr__(self) -> str:  # pragma: no cover
        return f"LongTermMemory(files={list(self.files.keys())})"


__all__ = ["LongTermMemory"]
