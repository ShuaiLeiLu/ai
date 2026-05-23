"""
LLM 客户端 —— 基于 httpx 实现 OpenAI 兼容的聊天补全

新增能力(2026-05-22 重构):
  - profile 机制:同一客户端按 profile 切换 base_url/api_key/model,
    数据型 skill 走便宜模型,综合型 skill 走强模型,无需新建实例
  - chat_stream():异步流式生成,供 SSE 端点使用
  - chat() 保持向后兼容,内部统一走 profile=default

使用方式:
  client = get_llm_client()
  reply = await client.chat([...], profile="data")
  async for chunk in client.chat_stream([...], profile="synthesis"):
      print(chunk, end="")
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class LLMMessage:
    role: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class LLMProfile:
    """一个 profile = 一组 base_url + api_key + model + 默认参数。"""

    name: str
    base_url: str = ""
    api_key: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 2048
    timeout: float = 90.0

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key)


def _load_profiles() -> dict[str, LLMProfile]:
    """从 Settings 装配 default / data / synthesis 三个 profile。

    data 和 synthesis 任一字段缺省时回退到 default。
    """
    s = get_settings()
    default = LLMProfile(
        name="default",
        base_url=s.openai_base_url or "",
        api_key=s.openai_api_key or "",
        model=s.openai_model or "gpt-4o-mini",
    )
    data = LLMProfile(
        name="data",
        base_url=s.llm_data_base_url or default.base_url,
        api_key=s.llm_data_api_key or default.api_key,
        model=s.llm_data_model or default.model,
        temperature=0.4,  # 数据 skill 偏稳定
        max_tokens=1500,
    )
    synthesis = LLMProfile(
        name="synthesis",
        base_url=s.llm_synthesis_base_url or default.base_url,
        api_key=s.llm_synthesis_api_key or default.api_key,
        model=s.llm_synthesis_model or default.model,
        temperature=0.7,  # 综合 skill 需要发散
        max_tokens=4096,
    )
    return {"default": default, "data": data, "synthesis": synthesis}


class LLMClient:
    """OpenAI 兼容的 LLM 客户端,支持多 profile + 流式。"""

    def __init__(self, profiles: dict[str, LLMProfile] | None = None) -> None:
        self._profiles: dict[str, LLMProfile] = profiles or _load_profiles()
        self._clients: dict[str, httpx.AsyncClient] = {}

    @property
    def is_configured(self) -> bool:
        """默认 profile 是否可用(向后兼容旧代码)。"""
        return self._profiles["default"].is_configured

    def get_profile(self, name: str) -> LLMProfile:
        if name not in self._profiles:
            logger.warning("未知 LLM profile=%s,回退 default", name)
            return self._profiles["default"]
        return self._profiles[name]

    def _get_http_client(self, profile: LLMProfile) -> httpx.AsyncClient:
        client = self._clients.get(profile.name)
        if client is None or client.is_closed:
            client = httpx.AsyncClient(
                base_url=profile.base_url.rstrip("/"),
                headers={
                    "Authorization": f"Bearer {profile.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(profile.timeout, connect=10.0),
            )
            self._clients[profile.name] = client
        return client

    def _build_payload(
        self,
        profile: LLMProfile,
        messages: list[LLMMessage],
        *,
        stream: bool,
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict:
        return {
            "model": profile.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature if temperature is not None else profile.temperature,
            "max_tokens": max_tokens if max_tokens is not None else profile.max_tokens,
            "stream": stream,
        }

    # ── 一次性回复 ──
    async def chat(
        self,
        messages: list[LLMMessage],
        *,
        profile: str = "default",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        prof = self.get_profile(profile)
        if not prof.is_configured:
            raise RuntimeError(f"LLM profile={prof.name} 未配置")
        client = self._get_http_client(prof)
        payload = self._build_payload(
            prof, messages, stream=False, temperature=temperature, max_tokens=max_tokens
        )
        try:
            resp = await client.post("/v1/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            logger.error(
                "LLM API 错误 profile=%s: %s %s",
                prof.name, e.response.status_code, e.response.text[:200],
            )
            raise
        except Exception as e:
            logger.error("LLM 请求失败 profile=%s: %s", prof.name, e)
            raise

    # ── 流式回复(SSE 友好)──
    async def chat_stream(
        self,
        messages: list[LLMMessage],
        *,
        profile: str = "default",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """逐块 yield 文本片段。

        实现要点:
          - 走 OpenAI 兼容的 SSE 协议(每行 `data: <json>`,以 `data: [DONE]` 结束)
          - 出错时直接抛异常,由上层 SSE 包装错误事件
        """
        prof = self.get_profile(profile)
        if not prof.is_configured:
            raise RuntimeError(f"LLM profile={prof.name} 未配置")
        client = self._get_http_client(prof)
        payload = self._build_payload(
            prof, messages, stream=True, temperature=temperature, max_tokens=max_tokens
        )
        async with client.stream(
            "POST", "/v1/chat/completions", json=payload
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                logger.error(
                    "LLM 流式 API 错误 profile=%s: %s %s",
                    prof.name, resp.status_code, body[:200],
                )
                raise httpx.HTTPStatusError(
                    f"LLM stream failed: {resp.status_code}",
                    request=resp.request, response=resp,
                )
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload_text = line[5:].strip()
                if payload_text == "[DONE]":
                    return
                try:
                    chunk = json.loads(payload_text)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    yield content

    async def close(self) -> None:
        for client in self._clients.values():
            if not client.is_closed:
                await client.aclose()
        self._clients.clear()


_llm_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
