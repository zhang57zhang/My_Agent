"""Provider 注册表 — 根据 ProviderConfig 创建对应的 Provider 实例."""

from __future__ import annotations

import logging

from myagent.core.models import ProviderConfig
from myagent.providers.base import Provider
from myagent.providers.openai_compat import OpenAICompatProvider
from myagent.providers.qwen import QwenProvider
from myagent.providers.zhipu import ZhipuProvider

logger = logging.getLogger(__name__)

# Provider 注册表：provider_id → Provider 类
_REGISTRY: dict[str, type[OpenAICompatProvider]] = {
    "zhipu": ZhipuProvider,
    "qwen": QwenProvider,
    "openai": OpenAICompatProvider,
}


def register_provider(provider_id: str, provider_cls: type[OpenAICompatProvider]) -> None:
    """注册新的 Provider 类."""
    _REGISTRY[provider_id] = provider_cls
    logger.info(f"Registered provider: {provider_id}")


def create_provider(config: ProviderConfig) -> Provider:
    """根据配置创建 Provider 实例.

    Args:
        config: Provider 配置，包含 provider_id、model_id、api_key 等.

    Returns:
        对应的 Provider 实例.

    Raises:
        ValueError: 未知的 provider_id.
    """
    cls = _REGISTRY.get(config.provider_id)
    if cls is None:
        available = ", ".join(_REGISTRY.keys())
        raise ValueError(f"Unknown provider: '{config.provider_id}'. Available: {available}")

    logger.info(f"Creating provider: {config.provider_id}/{config.model_id}")
    return cls(
        model=config.model_id,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        top_p=config.top_p,
    )


def list_providers() -> list[str]:
    """列出所有已注册的 Provider ID."""
    return list(_REGISTRY.keys())


__all__ = ["create_provider", "register_provider", "list_providers"]
