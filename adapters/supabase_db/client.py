from __future__ import annotations

from typing import Any

import httpx

from core.errors import AppError, ErrorCode


class SupabaseRestClient:
    """HTTP PostgREST client enforcing user JWT + RLS on every call (ADR-011, ADR-015)."""

    def __init__(self, supabase_url: str, publishable_key: str, timeout_seconds: float = 8.0) -> None:
        self._base_url = supabase_url.rstrip("/")
        self._publishable_key = publishable_key
        self._timeout = timeout_seconds

    def _headers(self, access_token: str, prefer: str | None = None, schema: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self._publishable_key,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        if schema:
            headers["Accept-Profile"] = schema
            headers["Content-Profile"] = schema
        return headers

    def request(
        self,
        method: str,
        path: str,
        access_token: str,
        params: dict[str, str] | None = None,
        json_body: Any = None,
        prefer: str | None = None,
        schema: str | None = None,
    ) -> Any:
        if not self._base_url or not self._publishable_key:
            raise AppError(
                code=ErrorCode.SUPABASE_UNAVAILABLE,
                message="Configuracao do Supabase ausente no servidor local.",
                http_status=503,
                retryable=True,
                details={"next_action": "Verifique NEXT_PUBLIC_SUPABASE_URL e NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY."},
            )
        url = f"{self._base_url}/rest/v1/{path.lstrip('/')}"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.request(
                    method=method,
                    url=url,
                    headers=self._headers(access_token, prefer=prefer, schema=schema),
                    params=params,
                    json=json_body,
                )
        except httpx.RequestError as exc:
            raise AppError(
                code=ErrorCode.SUPABASE_UNAVAILABLE,
                message="Supabase inacessivel ou sem conectividade de rede.",
                http_status=503,
                retryable=True,
                details={"next_action": "Verifique sua conexao e tente novamente."},
            ) from exc

        if resp.status_code >= 500:
            raise AppError(
                code=ErrorCode.SUPABASE_UNAVAILABLE,
                message="Supabase retornou indisponibilidade temporaria.",
                http_status=503,
                retryable=True,
                details={"next_action": "Aguarde alguns instantes e tente novamente."},
            )
        if resp.status_code == 401:
            raise AppError(
                code=ErrorCode.AUTH_UNAUTHENTICATED,
                message="Sessao rejeitada pelo Supabase.",
                http_status=401,
            )
        if resp.status_code == 403:
            raise AppError(
                code=ErrorCode.WORKSPACE_FORBIDDEN,
                message="Acesso bloqueado pelas politicas RLS do workspace.",
                http_status=403,
            )
        if resp.status_code == 409:
            raise AppError(
                code=ErrorCode.VERSION_CONFLICT,
                message="Conflito de unicidade ou versao ao persistir no Supabase.",
                http_status=409,
                retryable=True,
            )
        if resp.status_code >= 400:
            raise AppError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Erro ao processar operacao no Supabase.",
                http_status=422,
                details={"status_code": resp.status_code},
            )
        if not resp.content:
            return None
        return resp.json()

    def check_health(self) -> bool:
        if not self._base_url or not self._publishable_key:
            return False
        try:
            with httpx.Client(timeout=4.0) as client:
                resp = client.get(
                    f"{self._base_url}/auth/v1/settings",
                    headers={"apikey": self._publishable_key},
                )
                return resp.status_code < 500
        except httpx.RequestError:
            return False
