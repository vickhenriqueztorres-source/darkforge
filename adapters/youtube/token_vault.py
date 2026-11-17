from __future__ import annotations

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from core.errors import AppError, ErrorCode


class TokenVault:
    """AES-256-GCM encryption for OAuth tokens at rest (key never stored with token)."""

    def __init__(self, key_b64: str) -> None:
        raw = key_b64.strip()
        if not raw:
            self._key: bytes | None = None
            return
        try:
            decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        except Exception as exc:
            raise AppError(ErrorCode.VALIDATION_ERROR, "TOKEN_ENCRYPTION_KEY invalida.", http_status=500) from exc
        if len(decoded) != 32:
            raise AppError(ErrorCode.VALIDATION_ERROR, "TOKEN_ENCRYPTION_KEY deve ter 32 bytes.", http_status=500)
        self._key = decoded

    def encrypt(self, plaintext: str) -> str:
        if self._key is None:
            raise AppError(
                ErrorCode.OAUTH_REQUIRED_OR_REVOKED,
                "TOKEN_ENCRYPTION_KEY ausente; reconexao OAuth necessaria.",
                http_status=500,
            )
        nonce = os.urandom(12)
        ct = AESGCM(self._key).encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.urlsafe_b64encode(nonce + ct).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        if self._key is None:
            raise AppError(
                ErrorCode.OAUTH_REQUIRED_OR_REVOKED,
                "Chave de criptografia perdida ou ausente; reconecte o canal YouTube.",
                http_status=401,
                details={"next_action": "Reconecte a conta YouTube via OAuth."},
            )
        try:
            raw = base64.urlsafe_b64decode(ciphertext + "=" * (-len(ciphertext) % 4))
            nonce, ct = raw[:12], raw[12:]
            return AESGCM(self._key).decrypt(nonce, ct, None).decode("utf-8")
        except (InvalidTag, Exception) as exc:
            raise AppError(
                ErrorCode.OAUTH_REQUIRED_OR_REVOKED,
                "Nao foi possivel descriptografar token OAuth; reconexao obrigatoria.",
                http_status=401,
                details={"next_action": "Reconecte a conta YouTube via OAuth."},
            ) from exc
