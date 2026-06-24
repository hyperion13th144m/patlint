"""AI client wrappers for Anthropic and Ollama."""
from __future__ import annotations

import json
import os
from typing import Any, Protocol


TokenUsage = dict[str, int]  # {"input_tokens": int, "output_tokens": int}


def _zero_usage() -> TokenUsage:
    return {"input_tokens": 0, "output_tokens": 0}


class AIClient(Protocol):
    async def chat(self, system: str, user: str) -> tuple[str, TokenUsage]:
        ...


class AnthropicClient:
    def __init__(self, model: str | None = None) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic パッケージが必要です: pip install 'patlint[ai]'"
            ) from exc

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("環境変数 ANTHROPIC_API_KEY が設定されていません。")

        self._model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def chat(self, system: str, user: str) -> tuple[str, TokenUsage]:
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        usage: TokenUsage = {
            "input_tokens": message.usage.input_tokens,
            "output_tokens": message.usage.output_tokens,
        }
        return message.content[0].text, usage


class OllamaClient:
    def __init__(self, model: str = "qwen3:8b", base_url: str | None = None) -> None:
        try:
            import httpx  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "httpx パッケージが必要です: pip install 'patlint[ai]'"
            ) from exc

        self._model = model
        self._base_url = base_url or os.environ.get(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )

    async def chat(self, system: str, user: str) -> tuple[str, TokenUsage]:
        import httpx

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self._base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        usage: TokenUsage = {
            "input_tokens": data.get("prompt_eval_count", 0),
            "output_tokens": data.get("eval_count", 0),
        }
        return data["message"]["content"], usage


def get_ai_client(provider: str = "anthropic", model: str | None = None) -> AIClient:
    if provider == "anthropic":
        return AnthropicClient(model=model)
    if provider == "ollama":
        return OllamaClient(model=model or "qwen3:8b")
    raise ValueError(f"不明なプロバイダー: {provider}。'anthropic' または 'ollama' を指定してください。")
