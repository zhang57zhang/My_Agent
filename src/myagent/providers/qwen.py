"""阿里通义千问 Provider 适配器.

通义千问提供 OpenAI 兼容 API：
- Base URL: https://dashscope.aliyuncs.com/compatible-mode/v1
- 支持模型: qwen-plus, qwen-turbo, qwen-max 等
"""

from __future__ import annotations

from myagent.providers.openai_compat import OpenAICompatProvider


class QwenProvider(OpenAICompatProvider):
    """阿里通义千问 Provider."""

    PROVIDER_ID = "qwen"
    DEFAULT_MODEL = "qwen-plus"
    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
