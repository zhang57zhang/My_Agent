"""安全模块 — 风险评估、审批流程、输入验证."""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any

from myagent.core.models import RiskLevel

logger = logging.getLogger(__name__)


class ApprovalDecision(str, Enum):
    """审批决策."""

    APPROVE = "approve"
    DENY = "deny"
    NEEDS_CONFIRM = "needs_confirm"


# 提示注入攻击模式
INJECTION_PATTERNS = [
    r"ignore\s+(previous|prior)\s+(instructions?|prompt)",
    r"do\s+not\s+tell\s+the\s+user",
    r"system\s+prompt\s+override",
    r"you\s+are\s+now",
    r"new\s+instructions?\s*:",
    r"forget\s+everything",
    r"disregard\s+(all|previous|your)",
]

# 危险文件路径模式
DANGEROUS_PATHS = [
    "/etc/passwd",
    "/etc/shadow",
    "/etc/sudoers",
    "C:\\Windows\\System32",
    "~/.ssh/id_rsa",
    "~/.aws/credentials",
    ".env",
    "credentials.json",
    "id_rsa",
]


class SafetyChecker:
    """安全检查器.

    提供：
    - 工具调用风险评估
    - 提示注入检测
    - 路径安全验证
    - 审批流程
    """

    def __init__(
        self,
        auto_approve_low_risk: bool = True,
        auto_deny_dangerous: bool = True,
    ) -> None:
        self.auto_approve_low_risk = auto_approve_low_risk
        self.auto_deny_dangerous = auto_deny_dangerous

    def assess_tool_call(self, tool_name: str, args: dict[str, Any]) -> ApprovalDecision:
        """评估工具调用的安全风险.

        Args:
            tool_name: 工具名称.
            args: 工具参数.

        Returns:
            审批决策.
        """
        # 文件操作风险检查
        if tool_name == "file":
            path = args.get("path", "")
            action = args.get("action", "")

            if self._is_dangerous_path(path):
                logger.warning(f"Blocked dangerous path access: {path}")
                return ApprovalDecision.DENY

            if action == "write":
                return ApprovalDecision.NEEDS_CONFIRM

        # Shell 命令风险检查
        if tool_name == "bash":
            command = args.get("command", "")
            if self._is_dangerous_command(command):
                logger.warning(f"Blocked dangerous command: {command}")
                return ApprovalDecision.DENY
            return ApprovalDecision.NEEDS_CONFIRM

        # 低风险工具自动通过
        if self.auto_approve_low_risk:
            return ApprovalDecision.APPROVE

        return ApprovalDecision.NEEDS_CONFIRM

    def check_prompt_injection(self, text: str) -> list[str]:
        """检测文本中的提示注入攻击模式.

        Args:
            text: 待检测文本.

        Returns:
            匹配到的攻击模式列表.
        """
        threats: list[str] = []
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                threats.append(pattern)
        return threats

    def check_input_safety(self, user_input: str) -> list[str]:
        """综合检查用户输入安全性.

        Args:
            user_input: 用户输入文本.

        Returns:
            安全警告列表.
        """
        warnings: list[str] = []

        # 检查提示注入
        injections = self.check_prompt_injection(user_input)
        if injections:
            warnings.append(f"Detected {len(injections)} potential prompt injection pattern(s)")

        # 检查超长输入（可能是注入载荷）
        if len(user_input) > 50000:
            warnings.append(f"Input is very long ({len(user_input)} chars)")

        # 检查隐形 Unicode
        invisible_chars = self._detect_invisible_unicode(user_input)
        if invisible_chars:
            warnings.append(f"Detected {len(invisible_chars)} invisible Unicode character(s)")

        return warnings

    # ── 内部方法 ────────────────────────────────────────────

    @staticmethod
    def _is_dangerous_path(path: str) -> bool:
        """检查是否为危险路径."""
        from pathlib import Path

        try:
            p = Path(path).resolve()
            for dp in DANGEROUS_PATHS:
                if dp.replace("~", str(Path.home())) in str(p):
                    return True
        except (OSError, ValueError):
            pass
        return False

    @staticmethod
    def _is_dangerous_command(command: str) -> bool:
        """检查是否为危险命令."""
        cmd_lower = command.lower().strip()
        dangerous = [
            "rm -rf /",
            "rm -rf /*",
            "mkfs",
            "dd if=/dev/zero",
            "shutdown",
            "reboot",
            "halt",
            ":(){ :|:& };:",
            "format ",
            "del /f /s /q C:",
        ]
        for d in dangerous:
            if d in cmd_lower:
                return True
        return False

    @staticmethod
    def _detect_invisible_unicode(text: str) -> list[str]:
        """检测隐形 Unicode 字符."""
        invisible_ranges = [
            (0x200B, 0x200F),  # Zero-width characters
            (0x2060, 0x206F),  # Invisible format characters
            (0xFEFF, 0xFEFF),  # BOM
            (0x202A, 0x202E),  # Bidirectional control
        ]
        found: list[str] = []
        for char in text:
            code = ord(char)
            for start, end in invisible_ranges:
                if start <= code <= end:
                    found.append(f"U+{code:04X}")
        return found


__all__ = ["SafetyChecker", "ApprovalDecision"]
