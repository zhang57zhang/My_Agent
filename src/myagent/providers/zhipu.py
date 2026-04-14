"""智谱 GLM Provider 适配器.

智谱 AI 提供 OpenAI 兼容 API：
- Base URL: https://open.bigmodel.cn/api/paas/v4
- 支持模型: glm-4-plus, glm-4-flash, glm-4-long 等
"""

from __future__ import annotations

from myagent.providers.openai_compat import OpenAICompatProvider


class ZhipuProvider(OpenAICompatProvider):
    """智谱 GLM 模型 Provider."""

    PROVIDER_ID = "zhipu"
    DEFAULT_MODEL = "glm-4-plus"
    DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
