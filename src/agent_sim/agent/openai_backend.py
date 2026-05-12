"""OpenAI LLM backend with async client support."""
from __future__ import annotations

import logging
import os
from typing import Any

from agent_sim.agent.llm_agent import LLMBackend

logger = logging.getLogger(__name__)


class OpenAIBackend(LLMBackend):
    """OpenAI API 后端。

    使用 OpenAI Python SDK 进行 LLM 调用。支持所有 OpenAI 兼容的 API 端点。

    Attributes:
        model: 模型名称
        api_key: API 密钥（默认从 OPENAI_API_KEY 环境变量读取）
        base_url: API 基础 URL（支持 OpenAI 兼容端点）
        temperature: 生成温度
        max_tokens: 最大生成 token 数
        timeout: 请求超时时间（秒）

    Example:
        >>> backend = OpenAIBackend(
        ...     model="gpt-4o-mini",
        ...     api_key="sk-...",
        ... )
        >>> response = await backend.generate([{"role": "user", "content": "hello"}])
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        timeout: float = 60.0,
        **kwargs: Any,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.extra_kwargs = kwargs
        self._client: Any = None

    def _get_client(self) -> Any:
        """懒加载 OpenAI 异步客户端。"""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError(
                    "需要安装 openai 包: pip install openai"
                ) from None
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def generate(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """调用 OpenAI API 生成响应。

        Args:
            messages: 对话消息列表
            **kwargs: 覆盖默认参数（model, temperature 等）

        Returns:
            生成的文本

        Raises:
            RuntimeError: API 调用失败
        """
        client = self._get_client()
        params = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }
        params.update(self.extra_kwargs)

        try:
            response = await client.chat.completions.create(**params)
            content = response.choices[0].message.content or ""
            logger.debug(
                "OpenAI response: model=%s, tokens=%s",
                response.model,
                response.usage.total_tokens if response.usage else "unknown",
            )
            return content
        except Exception as e:
            logger.error("OpenAI API 调用失败: %s", e)
            raise RuntimeError(f"OpenAI API 调用失败: {e}") from e

    async def close(self) -> None:
        """关闭客户端连接。"""
        if self._client:
            await self._client.close()
            self._client = None
