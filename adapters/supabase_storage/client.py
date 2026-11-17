from __future__ import annotations

import hashlib
from uuid import UUID

import httpx

from core.errors import AppError, ErrorCode
from core.jobs.models import ReconcileReport, StorageObjectRecord, StorageObjectStatus
from core.jobs.ports import StorageMetadataPort


class SupabaseStorageClient:
    """Private Supabase Storage client (ADR-012). Enforces workspace-prefixed paths and checksums."""

    def __init__(self, supabase_url: str, publishable_key: str, service_role_key: str = "", timeout_seconds: float = 15.0) -> None:
        self._base_url = supabase_url.rstrip("/")
        self._pub_key = publishable_key
        self._srv_key = service_role_key
        self._timeout = timeout_seconds

    def _auth_headers(self, token: str, content_type: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self._pub_key,
            "Authorization": f"Bearer {token}",
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def upload_object(
        self,
        access_token: str,
        bucket: str,
        object_path: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Uploads object bytes and returns sha256 hex."""
        url = f"{self._base_url}/storage/v1/object/{bucket}/{object_path.lstrip('/')}"
        headers = self._auth_headers(access_token, content_type=content_type)
        headers["x-upsert"] = "true"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(url, headers=headers, content=data)
        except httpx.RequestError as exc:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Storage inacessivel durante upload.", http_status=503, retryable=True) from exc

        if resp.status_code in (401, 403):
            raise AppError(ErrorCode.WORKSPACE_FORBIDDEN, "Storage bloqueou upload por politica RLS.", http_status=403)
        if resp.status_code >= 500:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Erro remoto no Supabase Storage.", http_status=503, retryable=True)
        if resp.status_code >= 400:
            raise AppError(ErrorCode.VALIDATION_ERROR, f"Falha no upload para Storage ({resp.status_code}).", http_status=422)
        return hashlib.sha256(data).hexdigest()

    def download_bytes(self, access_token: str, bucket: str, object_path: str) -> bytes:
        url = f"{self._base_url}/storage/v1/object/{bucket}/{object_path.lstrip('/')}"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url, headers=self._auth_headers(access_token))
        except httpx.RequestError as exc:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Storage inacessivel durante download.", http_status=503, retryable=True) from exc
        if resp.status_code in (401, 403):
            raise AppError(ErrorCode.WORKSPACE_FORBIDDEN, "Acesso negado ao objeto no Storage.", http_status=403)
        if resp.status_code == 404 or (resp.status_code == 400 and "not_found" in resp.text.lower()):
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Objeto nao encontrado no Storage.", http_status=404)
        if resp.status_code >= 400:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, f"Erro ao baixar objeto ({resp.status_code}).", http_status=503, retryable=True)
        return resp.content

    def create_signed_url(self, access_token: str, bucket: str, object_path: str, expires_in: int = 60) -> str:
        url = f"{self._base_url}/storage/v1/object/sign/{bucket}/{object_path.lstrip('/')}"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(
                    url,
                    headers=self._auth_headers(access_token, content_type="application/json"),
                    json={"expiresIn": max(10, min(expires_in, 300))},
                )
        except httpx.RequestError as exc:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Storage inacessivel ao assinar URL.", http_status=503, retryable=True) from exc
        if resp.status_code in (401, 403, 400, 404):
            raise AppError(ErrorCode.WORKSPACE_FORBIDDEN, "Nao autorizado a gerar signed URL para este objeto.", http_status=403)
        data = resp.json()
        signed = data.get("signedURL") or data.get("signedUrl") or ""
        if signed.startswith("/"):
            return f"{self._base_url}/storage/v1{signed}"
        return signed

    def list_workspace_objects(self, bucket: str, workspace_id: UUID) -> list[str]:
        """Lists remote objects in `<workspace_id>/` using service role for reconciler audits."""
        token = self._srv_key
        if not token:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "SUPABASE_SERVICE_ROLE_KEY ausente para reconciler.", http_status=503)
        url = f"{self._base_url}/storage/v1/object/list/{bucket}"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(
                    url,
                    headers={"apikey": token, "Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json={"prefix": f"{workspace_id}/", "limit": 1000, "offset": 0},
                )
        except httpx.RequestError as exc:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Storage inacessivel durante listagem.", http_status=503, retryable=True) from exc
        if resp.status_code >= 400:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, f"Erro ao listar bucket {bucket}.", http_status=503, retryable=True)
        items = resp.json() or []
        return [f"{workspace_id}/{item['name']}" for item in items if item.get("name")]


class StorageService:
    """Coordinates Storage uploads, SHA-256 verification, and DB/Storage reconciliation (T-STO-001)."""

    def __init__(self, storage_client: SupabaseStorageClient, metadata_repo: StorageMetadataPort) -> None:
        self._storage = storage_client
        self._meta = metadata_repo

    def upload_and_verify_ready(
        self,
        access_token: str,
        workspace_id: UUID,
        bucket: str,
        opaque_name: str,
        data: bytes,
        content_type: str,
        actor_user_id: UUID,
        job_id: UUID | None = None,
        expected_sha256: str | None = None,
    ) -> StorageObjectRecord:
        if ".." in opaque_name or opaque_name.startswith("/"):
            raise AppError(ErrorCode.VALIDATION_ERROR, "Nome de objeto invalido (path traversal).", http_status=422)
        object_path = f"{workspace_id}/{opaque_name}"
        rec = self._meta.create_uploading_record(
            workspace_id=workspace_id,
            bucket=bucket,
            object_path=object_path,
            content_type=content_type,
            created_by=actor_user_id,
            created_by_job=job_id,
        )
        local_sha = hashlib.sha256(data).hexdigest()
        if expected_sha256 and local_sha != expected_sha256:
            self._meta.update_status(workspace_id, rec.id, StorageObjectStatus.FAILED)
            raise AppError(ErrorCode.STORAGE_CHECKSUM_MISMATCH, "Checksum local divergente.", http_status=422, retryable=True)

        self._storage.upload_object(access_token, bucket, object_path, data, content_type=content_type)
        self._meta.update_status(workspace_id, rec.id, StorageObjectStatus.VERIFYING, sha256=local_sha, size_bytes=len(data))

        # Re-read remote bytes to confirm integrity before promoting to READY
        remote_bytes = self._storage.download_bytes(access_token, bucket, object_path)
        remote_sha = hashlib.sha256(remote_bytes).hexdigest()
        if remote_sha != local_sha:
            self._meta.update_status(workspace_id, rec.id, StorageObjectStatus.FAILED)
            raise AppError(
                ErrorCode.STORAGE_CHECKSUM_MISMATCH,
                "Checksum remoto nao confere apos upload.",
                http_status=422,
                retryable=True,
            )
        return self._meta.update_status(
            workspace_id,
            rec.id,
            StorageObjectStatus.READY,
            sha256=remote_sha,
            size_bytes=len(remote_bytes),
        )

    def reconcile_bucket(self, workspace_id: UUID, bucket: str) -> ReconcileReport:
        db_records = self._meta.list_objects(workspace_id, bucket=bucket)
        remote_paths = set(self._storage.list_workspace_objects(bucket, workspace_id))
        db_by_path = {r.object_path: r for r in db_records}

        missing_in_storage: list[str] = []
        incomplete_uploads: list[str] = []
        for rec in db_records:
            if rec.status in (StorageObjectStatus.UPLOADING, StorageObjectStatus.VERIFYING):
                incomplete_uploads.append(rec.object_path)
            elif rec.status == StorageObjectStatus.READY and rec.object_path not in remote_paths:
                missing_in_storage.append(rec.object_path)

        orphaned_in_storage = sorted(p for p in remote_paths if p not in db_by_path)
        return ReconcileReport(
            workspace_id=workspace_id,
            bucket=bucket,
            missing_in_storage=sorted(missing_in_storage),
            orphaned_in_storage=orphaned_in_storage,
            incomplete_uploads=sorted(incomplete_uploads),
        )
