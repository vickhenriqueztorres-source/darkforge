"""Cliente OpenAI-compativel para o OmniRoute local (gateway de IA multi-modelo)."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from adapters.ai_providers.router import redact_sensitive_text
from core.errors import AppError, ErrorCode


def extract_json_object(raw_text: str) -> dict[str, Any]:
    """Extrai o primeiro objeto JSON valido de uma resposta de LLM (com ou sem cerca markdown)."""
    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        parsed = json.loads(text[start : end + 1])
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("Resposta do modelo nao contem um objeto JSON valido.")


class OmniRouteClient:
    """Cliente HTTP sincrono para OmniRoute (/v1/chat/completions)."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        default_model: str | None = None,
        fallback_model: str | None = "agy/gemini-3.1-flash-lite",
        timeout_seconds: float = 90.0,
        http_transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = (
            (base_url if base_url is not None else os.getenv("OMNIROUTE_BASE_URL", "http://127.0.0.1:20128/v1"))
            .strip()
            .rstrip("/")
        )
        self._api_key = (api_key if api_key is not None else os.getenv("OMNIROUTE_API_KEY", "")).strip()
        self._default_model = (
            (default_model if default_model is not None else os.getenv("OMNIROUTE_MODEL", "agy/claude-sonnet-4-6"))
            .strip()
            or "agy/claude-sonnet-4-6"
        )
        self._fallback_model = (fallback_model or "").strip() or None
        self._timeout = float(timeout_seconds)
        self._transport = http_transport

    @property
    def is_configured(self) -> bool:
        return bool(self._base_url and self._api_key)

    @property
    def default_model(self) -> str:
        return self._default_model

    def _post_completion(
        self,
        selected_model: str,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float,
        max_tokens: int,
    ) -> tuple[dict[str, Any], str]:
        payload = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        try:
            timeout_cfg = httpx.Timeout(self._timeout, connect=10.0)
            with httpx.Client(timeout=timeout_cfg, transport=self._transport) as client:
                resp = client.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.RequestError as exc:
            raise AppError(
                ErrorCode.AI_PROVIDER_UNAVAILABLE,
                f"Falha de rede/timeout ao chamar OmniRoute: {redact_sensitive_text(str(exc))[:140]}",
                http_status=503,
                retryable=True,
            ) from exc

        if resp.status_code >= 400:
            raise AppError(
                ErrorCode.AI_PROVIDER_UNAVAILABLE,
                f"OmniRoute retornou HTTP {resp.status_code}: {redact_sensitive_text(resp.text)[:160]}",
                http_status=503,
                retryable=resp.status_code >= 500 or resp.status_code == 429,
            )

        try:
            body = resp.json()
            content = body["choices"][0]["message"]["content"]
            used_model = str(body.get("model") or selected_model)
            parsed = extract_json_object(str(content or ""))
            return parsed, used_model
        except Exception as exc:
            raise AppError(
                ErrorCode.AI_PROVIDER_UNAVAILABLE,
                f"Resposta JSON invalida do OmniRoute: {redact_sensitive_text(str(exc))[:140]}",
                http_status=503,
                retryable=True,
            ) from exc

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.35,
        max_tokens: int = 1800,
    ) -> tuple[dict[str, Any], str]:
        """Executa chat completion e retorna (json_dict, model_usado)."""
        if not self.is_configured:
            raise AppError(
                ErrorCode.AI_PROVIDER_UNAVAILABLE,
                "OmniRoute nao configurado (defina OMNIROUTE_API_KEY).",
                http_status=503,
                retryable=True,
            )

        selected_model = (model or self._default_model).strip()
        try:
            return self._post_completion(
                selected_model,
                system_prompt,
                user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except AppError:
            if model is None and self._fallback_model and self._fallback_model != selected_model:
                return self._post_completion(
                    self._fallback_model,
                    system_prompt,
                    user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            raise
