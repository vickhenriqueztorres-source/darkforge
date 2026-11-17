from __future__ import annotations

from uuid import UUID

import httpx
import jwt
from jwt import PyJWKClient

from core.errors import AppError, ErrorCode
from core.workspaces.models import AuthenticatedUser


class SupabaseJWTVerifier:
    """Validates Supabase Auth JWTs (strictly separated from YouTube OAuth)."""

    def __init__(
        self,
        supabase_url: str,
        jwt_secret: str = "",
        timeout_seconds: float = 5.0,
    ) -> None:
        self._supabase_url = supabase_url.rstrip("/")
        self._jwt_secret = jwt_secret
        self._timeout = timeout_seconds
        self._jwks_client = (
            PyJWKClient(f"{self._supabase_url}/auth/v1/.well-known/jwks.json", timeout=timeout_seconds)
            if self._supabase_url
            else None
        )

    def verify_token(self, token: str) -> AuthenticatedUser:
        if not token or not token.strip():
            raise AppError(
                code=ErrorCode.AUTH_UNAUTHENTICATED,
                message="Sessao ausente. Autentique-se antes de acessar o workspace.",
                http_status=401,
            )

        clean_token = token.strip()
        try:
            header = jwt.get_unverified_header(clean_token)
        except jwt.PyJWTError as exc:
            raise AppError(
                code=ErrorCode.AUTH_UNAUTHENTICATED,
                message="Token de sessao malformado.",
                http_status=401,
            ) from exc

        alg = str(header.get("alg", ""))
        try:
            if alg == "HS256":
                if not self._jwt_secret:
                    raise AppError(
                        code=ErrorCode.AUTH_UNAUTHENTICATED,
                        message="SUPABASE_JWT_SECRET nao configurado para validar tokens HS256.",
                        http_status=401,
                    )
                claims = jwt.decode(
                    clean_token,
                    self._jwt_secret,
                    algorithms=["HS256"],
                    audience="authenticated",
                    leeway=30,
                )
            elif alg in ("RS256", "ES256") and self._jwks_client is not None:
                signing_key = self._jwks_client.get_signing_key_from_jwt(clean_token)
                claims = jwt.decode(
                    clean_token,
                    signing_key.key,
                    algorithms=[alg],
                    audience="authenticated",
                    leeway=30,
                )
            else:
                raise AppError(
                    code=ErrorCode.AUTH_UNAUTHENTICATED,
                    message="Algoritmo JWT nao suportado para autenticacao.",
                    http_status=401,
                )
        except jwt.ExpiredSignatureError as exc:
            raise AppError(
                code=ErrorCode.AUTH_UNAUTHENTICATED,
                message="Sessao expirada. Faca login novamente.",
                http_status=401,
            ) from exc
        except jwt.PyJWTError as exc:
            raise AppError(
                code=ErrorCode.AUTH_UNAUTHENTICATED,
                message="Sessao invalida ou revogada.",
                http_status=401,
            ) from exc
        except httpx.HTTPError as exc:
            raise AppError(
                code=ErrorCode.SUPABASE_UNAVAILABLE,
                message="Nao foi possivel validar chaves de sessao no Supabase.",
                http_status=503,
                retryable=True,
            ) from exc

        sub = claims.get("sub")
        if not sub:
            raise AppError(
                code=ErrorCode.AUTH_UNAUTHENTICATED,
                message="Token sem identificador de usuario (sub).",
                http_status=401,
            )
        try:
            user_id = UUID(str(sub))
        except ValueError as exc:
            raise AppError(
                code=ErrorCode.AUTH_UNAUTHENTICATED,
                message="Identificador de usuario invalido no token.",
                http_status=401,
            ) from exc

        return AuthenticatedUser(
            user_id=user_id,
            email=claims.get("email"),
            access_token=clean_token,
        )
