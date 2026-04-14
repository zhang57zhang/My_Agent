"""意图识别模块 — 对用户消息进行意图分类."""

from __future__ import annotations

import re
import logging
from typing import Any

from myagent.core.models import IntentType

logger = logging.getLogger(__name__)

# 意图关键词映射（按优先级排序）
_INTENT_RULES: list[tuple[IntentType, list[str]]] = [
    (
        IntentType.FIX,
        ["error", "错误", "bug", "报错", "失败", "broken", "crash", "崩溃", "异常", "exception"],
    ),
    (
        IntentType.IMPLEMENT,
        [
            "implement",
            "实现",
            "添加",
            "add",
            "create",
            "创建",
            "write",
            "编写",
            "build",
            "构建",
            "make",
            "fix",
            "change",
            "修改",
            "update",
            "更新",
        ],
    ),
    (
        IntentType.INVESTIGATE,
        ["look into", "看看", "check", "检查", "investigate", "调查", "find", "找到", "search"],
    ),
    (
        IntentType.REFACTOR,
        [
            "refactor",
            "重构",
            "optimize",
            "优化",
            "clean up",
            "清理",
            "improve",
            "改进",
            "restructure",
        ],
    ),
    (
        IntentType.EVALUATE,
        [
            "what do you think",
            "你觉得",
            "should i",
            "是否应该",
            "compare",
            "对比",
            "evaluate",
            "评估",
        ],
    ),
    (
        IntentType.RESEARCH,
        [
            "explain",
            "解释",
            "how does",
            "怎么工作",
            "what is",
            "什么是",
            "why",
            "为什么",
            "describe",
        ],
    ),
]


def classify_intent(message: str) -> IntentType:
    """对用户消息进行意图分类.

    使用基于规则的关键词匹配，从最高优先级规则开始匹配。
    如果没有匹配到任何规则，返回 AMBIGUOUS。

    Args:
        message: 用户消息文本.

    Returns:
        意图类型.
    """
    msg_lower = message.lower().strip()

    # 空消息
    if not msg_lower:
        return IntentType.AMBIGUOUS

    # 疑问句检测（提高 RESEARCH/EVALUATE 优先级）
    is_question = msg_lower.endswith("?") or any(
        msg_lower.startswith(w)
        for w in ["怎么", "如何", "什么", "为什么", "how", "what", "why", "can", "could"]
    )

    for intent, keywords in _INTENT_RULES:
        for kw in keywords:
            if kw in msg_lower:
                # 如果是疑问句且匹配到 IMPLEMENT/FIX，检查是否真的是要求实施
                if is_question and intent in (IntentType.IMPLEMENT, IntentType.FIX):
                    # "how do I implement X?" → RESEARCH
                    # "fix this error" → FIX（不是疑问句形式）
                    if any(w in msg_lower for w in ["how", "怎么", "如何", "can i", "should i"]):
                        return IntentType.RESEARCH
                return intent

    return IntentType.AMBIGUOUS


def get_intent_guidance(intent: IntentType) -> str:
    """根据意图类型返回行为指导文本.

    Args:
        intent: 意图类型.

    Returns:
        行为指导文本（嵌入系统提示中）.
    """
    guidance = {
        IntentType.RESEARCH: (
            "用户提出研究/理解类问题。你的方法：探索 → 分析 → 回答。"
            "不要创建 Todo 列表，不要修改文件，只做研究和回答。"
        ),
        IntentType.IMPLEMENT: (
            "用户要求实施/修改。你的方法：规划 → 执行 → 验证。"
            "立即创建 Todo 列表，分解任务，然后逐步执行。"
        ),
        IntentType.INVESTIGATE: (
            "用户要求调查/检查。你的方法：探索 → 报告发现。"
            "搜索和分析代码库，报告你的发现，不要自行修改。"
        ),
        IntentType.EVALUATE: (
            "用户要求评估。你的方法：评估 → 提议 → 等待确认。"
            "给出你的分析和建议，但不要开始实施，等待用户确认。"
        ),
        IntentType.FIX: (
            "用户报告错误需要修复。你的方法：诊断 → 最小化修复。"
            "先理解错误，找到根因，然后做最小化的修复。不要趁机重构。"
        ),
        IntentType.REFACTOR: (
            "用户要求重构/优化。你的方法：先评估代码库 → 提出方案 → 等待确认。"
            "先了解现状，提出具体方案，不要盲目开始修改。"
        ),
        IntentType.AMBIGUOUS: ("用户意图不明确。你必须先向用户提出一个澄清问题，不要猜测意图。"),
    }
    return guidance.get(intent, "")


__all__ = ["classify_intent", "get_intent_guidance"]
