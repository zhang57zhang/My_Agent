"""会话管理 — 对话历史、上下文窗口、会话持久化."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from myagent.core.models import Message, MessageRole, SessionInfo

logger = logging.getLogger(__name__)


class SessionManager:
    """管理对话会话的生命周期.

    负责对话历史的存储、上下文窗口管理和会话持久化（JSONL 格式）。
    """

    def __init__(
        self,
        session_id: str | None = None,
        session_dir: Path | None = None,
        working_directory: str = ".",
        max_context_messages: int = 50,
    ) -> None:
        self.session_id = session_id or uuid.uuid4().hex[:12]
        self.working_directory = working_directory
        self.max_context_messages = max_context_messages

        # 会话存储目录
        self.session_dir = session_dir or Path.home() / ".myagent" / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # 会话日志文件
        self.session_file = self.session_dir / f"{self.session_id}.jsonl"

        # 对话历史
        self._messages: list[Message] = []

        # 加载已有会话
        self._load_session()

        # 会话元信息
        self._created_at = datetime.now().isoformat()
        self._updated_at = datetime.now().isoformat()

    @property
    def info(self) -> SessionInfo:
        """返回会话信息."""
        return SessionInfo(
            session_id=self.session_id,
            created_at=self._created_at,
            updated_at=self._updated_at,
            message_count=len(self._messages),
            working_directory=self.working_directory,
        )

    # ── 消息管理 ────────────────────────────────────────────

    def add_message(self, message: Message) -> None:
        """添加消息到对话历史."""
        self._messages.append(message)
        self._updated_at = datetime.now().isoformat()
        self._persist_message(message)

    def get_messages(self) -> list[Message]:
        """获取完整对话历史."""
        return list(self._messages)

    def get_context_messages(self, max_messages: int | None = None) -> list[Message]:
        """获取上下文窗口内的消息（最近的 N 条）.

        用于构建 LLM 请求的 messages 参数。自动处理上下文窗口裁剪。
        """
        limit = max_messages or self.max_context_messages
        # 保留系统消息（通常在开头），加上最近的 N 条
        system_msgs = [m for m in self._messages if m.role == MessageRole.SYSTEM]
        non_system = [m for m in self._messages if m.role != MessageRole.SYSTEM]
        recent = non_system[-limit:]
        return system_msgs + recent

    def get_last_user_message(self) -> Message | None:
        """获取最后一条用户消息."""
        for msg in reversed(self._messages):
            if msg.role == MessageRole.USER:
                return msg
        return None

    def get_last_assistant_message(self) -> Message | None:
        """获取最后一条助手消息."""
        for msg in reversed(self._messages):
            if msg.role == MessageRole.ASSISTANT:
                return msg
        return None

    def clear_history(self) -> None:
        """清空对话历史（保留系统消息）."""
        self._messages = [m for m in self._messages if m.role == MessageRole.SYSTEM]

    @property
    def message_count(self) -> int:
        """当前消息数量."""
        return len(self._messages)

    # ── 持久化 ──────────────────────────────────────────────

    def _load_session(self) -> None:
        """从 JSONL 文件加载历史会话."""
        if not self.session_file.exists():
            return

        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        msg = Message(**data)
                        self._messages.append(msg)
                    except (json.JSONDecodeError, Exception) as e:
                        logger.warning(f"Skipping corrupt message: {e}")
            logger.info(f"Loaded {len(self._messages)} messages from session {self.session_id}")
        except OSError as e:
            logger.error(f"Failed to load session: {e}")

    def _persist_message(self, message: Message) -> None:
        """将消息追加到 JSONL 文件."""
        try:
            with open(self.session_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(message.model_dump(), ensure_ascii=False) + "\n")
        except OSError as e:
            logger.error(f"Failed to persist message: {e}")

    # ── 会话生命周期 ────────────────────────────────────────

    def list_sessions(self) -> list[SessionInfo]:
        """列出所有会话."""
        sessions: list[SessionInfo] = []
        for filepath in self.session_dir.glob("*.jsonl"):
            try:
                session_id = filepath.stem
                stat = filepath.stat()
                sessions.append(
                    SessionInfo(
                        session_id=session_id,
                        created_at=datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        updated_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        message_count=sum(
                            1 for _ in filepath.open(encoding="utf-8", errors="ignore")
                        ),
                        working_directory="",
                    )
                )
            except OSError:
                continue
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """删除指定会话."""
        target = self.session_dir / f"{session_id}.jsonl"
        if target.exists():
            target.unlink()
            return True
        return False


__all__ = ["SessionManager"]
