"""Ollama Provider 适配器.

Ollama 提供原生 OpenAI 兼容 API：
- Base URL: http://localhost:11434/v1
- 支持模型: llama3, qwen2.5, deepseek-coder, mistral 等所有 Ollama 模型
- 认证: 无需 API Key（传任意值即可）
"""

from __future__ import annotations

import logging

import httpx
from openai import AsyncOpenAI

from myagent.providers.openai_compat import OpenAICompatProvider

logger = logging.getLogger(__name__)


class OllamaProvider(OpenAICompatProvider):
    """Ollama 本地/远程模型 Provider.

    通过 Ollama 的 OpenAI 兼容端点连接，支持 function calling、
    流式输出和 token 统计。无需真实 API Key。
    """

    PROVIDER_ID = "ollama"
    DEFAULT_MODEL = "qwen2.5"
    DEFAULT_BASE_URL = "http://localhost:11434/v1"

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str = "ollama",
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: float = 0.9,
        timeout: float = 120.0,
        ssl_verify: bool = True,
    ) -> None:
        self._model = model or self.DEFAULT_MODEL
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._top_p = top_p
        self._timeout = timeout
        self._base_url = base_url or self.DEFAULT_BASE_URL
        self._usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        # 自定义 httpx 客户端：控制超时和 SSL 验证
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0),
            verify=ssl_verify,
        )
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=self._base_url,
            http_client=http_client,
        )

    @property
    def provider_id(self) -> str:
        return self.PROVIDER_ID

    @property
    def model_id(self) -> str:
        return self._model

    def get_usage(self) -> dict[str, int]:
        return dict(self._usage)

    async def check_connection(self) -> dict:
        """检测 Ollama 服务是否可达，返回状态信息.

        使用独立 httpx 客户端调用 Ollama 原生 /api/tags 端点，
        不依赖 OpenAI SDK。

        Returns:
            {"reachable": bool, "host": str, "models": list[str]}
        """
        native_url = self._base_url.rstrip("/").removesuffix("/v1")
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(5.0, connect=3.0),
            ) as client:
                resp = await client.get(f"{native_url}/api/tags")
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m["name"] for m in data.get("models", [])]
                    return {
                        "reachable": True,
                        "host": native_url,
                        "models": models,
                    }
                return {
                    "reachable": False,
                    "host": native_url,
                    "models": [],
                }
        except Exception as e:
            logger.warning(f"Ollama 连接检测失败: {e}")
            return {
                "reachable": False,
                "host": native_url,
                "models": [],
                "error": str(e),
            }

    async def list_models(self) -> list[str]:
        """列出 Ollama 上所有可用模型.

        Returns:
            模型名称列表，如 ["llama3:latest", "qwen2.5:14b"]
        """
        result = await self.check_connection()
        return result.get("models", [])
