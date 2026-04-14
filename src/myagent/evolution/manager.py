"""自我进化系统 — 经验沉淀、技能自创、行为优化.

提供三种进化机制：
1. 经验沉淀：从每次交互中提取可复用模式
2. 技能自创：将重复工作流程提炼为可复用技能
3. 行为优化：定期回顾和调整自身行为参数
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from myagent.core.models import Message, MessageRole, ToolCall, ToolResult

logger = logging.getLogger(__name__)


class EvolutionManager:
    """自我进化管理器."""

    def __init__(self, lessons_dir: Path, skills_dir: Path) -> None:
        self.lessons_dir = lessons_dir
        self.skills_dir = skills_dir
        self.lessons_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    # ── 经验沉淀 ────────────────────────────────────────────

    def record_lesson(
        self,
        title: str,
        problem: str,
        solution: str,
        context: str = "",
    ) -> Path:
        """记录一条经验教训.

        Args:
            title: 经验标题.
            problem: 问题描述.
            solution: 解决方案.
            context: 上下文信息.

        Returns:
            保存的文件路径.
        """
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = title.lower().replace(" ", "-")[:40]
        filename = f"{timestamp}-{slug}.md"
        filepath = self.lessons_dir / filename

        content = f"""# {title}

**日期**: {datetime.now().strftime("%Y-%m-%d %H:%M")}

## 问题
{problem}

## 解决方案
{solution}

## 上下文
{context or "(无)"}
"""
        filepath.write_text(content, encoding="utf-8")
        logger.info(f"Recorded lesson: {title} → {filepath}")
        return filepath

    def get_recent_lessons(self, limit: int = 10) -> list[dict[str, str]]:
        """获取最近的经验教训."""
        lessons = []
        for filepath in sorted(self.lessons_dir.glob("*.md"), reverse=True)[:limit]:
            try:
                content = filepath.read_text(encoding="utf-8")
                title = ""
                for line in content.split("\n"):
                    if line.startswith("# "):
                        title = line[2:]
                        break
                lessons.append(
                    {
                        "title": title or filepath.stem,
                        "path": str(filepath),
                        "date": filepath.stem[:10],
                    }
                )
            except OSError:
                continue
        return lessons

    # ── 技能自创 ────────────────────────────────────────────

    def create_skill(
        self,
        name: str,
        description: str,
        trigger: str,
        steps: list[str],
        examples: list[str] | None = None,
    ) -> Path:
        """创建一个新技能.

        Args:
            name: 技能名称.
            description: 技能描述.
            trigger: 触发条件（什么时候使用此技能）.
            steps: 执行步骤列表.
            examples: 使用示例.

        Returns:
            保存的文件路径.
        """
        skill_dir = self.skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        filepath = skill_dir / "SKILL.md"

        steps_md = "\n".join(f"{i + 1}. {step}" for i, step in enumerate(steps))
        examples_md = "\n".join(f"- {ex}" for ex in examples) if examples else "(暂无)"

        content = f"""---
name: {name}
description: {description}
trigger: {trigger}
created: {datetime.now().strftime("%Y-%m-%d")}
---

# {name}

{description}

## 适用场景
{trigger}

## 执行步骤
{steps_md}

## 注意事项
- 执行前确认前置条件是否满足
- 每步执行后验证结果
- 如遇错误，参考经验教训

## 示例
{examples_md}
"""
        filepath.write_text(content, encoding="utf-8")
        logger.info(f"Created skill: {name} → {filepath}")
        return filepath

    def get_all_skills(self) -> list[dict[str, str]]:
        """获取所有已创建的技能."""
        skills = []
        for skill_dir in self.skills_dir.iterdir():
            skill_file = skill_dir / "SKILL.md"
            if skill_dir.is_dir() and skill_file.exists():
                try:
                    content = skill_file.read_text(encoding="utf-8")
                    skills.append(
                        {
                            "name": skill_dir.name,
                            "path": str(skill_file),
                            "description": self._extract_yaml_field(content, "description") or "",
                            "trigger": self._extract_yaml_field(content, "trigger") or "",
                        }
                    )
                except OSError:
                    continue
        return skills

    def should_create_skill(self, tool_calls: list[ToolCall], results: list[ToolResult]) -> bool:
        """判断是否应该从当前交互中创建技能.

        条件：工具调用次数 >= 5 且所有调用都成功。
        """
        if len(tool_calls) < 5:
            return False
        return all(not r.is_error for r in results)

    # ── 行为优化 ────────────────────────────────────────────

    def analyze_conversation(self, messages: list[Message]) -> dict[str, Any]:
        """分析对话记录，提取行为优化建议.

        Args:
            messages: 对话消息列表.

        Returns:
            分析结果.
        """
        stats: dict[str, Any] = {
            "total_messages": len(messages),
            "user_messages": 0,
            "assistant_messages": 0,
            "tool_calls": 0,
            "errors": 0,
            "repeated_patterns": [],
        }

        # 统计
        for msg in messages:
            if msg.role == MessageRole.USER:
                stats["user_messages"] += 1
            elif msg.role == MessageRole.ASSISTANT:
                stats["assistant_messages"] += 1
                if msg.tool_calls:
                    stats["tool_calls"] += len(msg.tool_calls)

        # 检测重复模式（简单实现：连续相同的工具调用）
        tool_sequence: list[str] = []
        for msg in messages:
            if msg.role == MessageRole.ASSISTANT and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_sequence.append(tc.function)

        # 检测 3+ 次连续重复的工具调用
        if len(tool_sequence) >= 3:
            for i in range(len(tool_sequence) - 2):
                if tool_sequence[i] == tool_sequence[i + 1] == tool_sequence[i + 2]:
                    stats["repeated_patterns"].append(f"3x consecutive '{tool_sequence[i]}' calls")

        return stats

    # ── 辅助方法 ────────────────────────────────────────────

    @staticmethod
    def _extract_yaml_field(content: str, field: str) -> str | None:
        """从 YAML frontmatter 中提取字段值."""
        if not content.startswith("---"):
            return None
        end = content.find("---", 3)
        if end == -1:
            return None
        yaml_text = content[3:end]
        for line in yaml_text.split("\n"):
            if line.startswith(f"{field}:"):
                return line[len(field) :].strip().strip('"').strip("'")
        return None


__all__ = ["EvolutionManager"]
