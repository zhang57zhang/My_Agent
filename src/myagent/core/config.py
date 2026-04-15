"""核心配置管理."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class MyAgentConfig(BaseModel):
    """MyAgent 全局配置."""

    # Provider
    default_provider: str = "zhipu"
    providers: dict[str, dict[str, str]] = Field(default_factory=dict)

    # Memory
    memory_dir: Path = Path.home() / ".myagent"
    max_memory_tokens: int = 800

    # Tools
    default_risk_level: str = "low"
    require_confirmation_for_high_risk: bool = True

    # Session
    session_dir: Path = Path.home() / ".myagent" / "sessions"
    max_context_messages: int = 50

    # Evolution
    skills_dir: Path = Path.home() / ".myagent" / "skills"
    lessons_dir: Path = Path.home() / ".myagent" / "lessons-learned"
    auto_create_skills: bool = True
    min_tool_calls_for_skill: int = 5

    # UI
    theme: str = "monokai"
    show_thinking: bool = False

    # Ollama
    ollama_host: str = "localhost"
    ollama_port: int = 11434
    ollama_timeout: float = 120.0

    @classmethod
    def load(cls, config_path: Path | None = None) -> MyAgentConfig:
        """从配置文件加载，不存在则使用默认值."""
        config_path = config_path or Path.home() / ".myagent" / "config.yaml"
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return cls(**data)
        return cls()

    def save(self, config_path: Path | None = None) -> None:
        """保存配置到文件."""
        config_path = config_path or Path.home() / ".myagent" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                self.model_dump(exclude_defaults=True),
                f,
                default_flow_style=False,
                allow_unicode=True,
            )
