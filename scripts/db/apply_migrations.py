from __future__ import annotations

import hashlib
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = ROOT / "migrations"


def apply_all() -> list[str]:
    load_dotenv(ROOT / ".env")
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL nao configurada em .env")

    applied: list[str] = []
    with psycopg.connect(dsn, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS app;")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS app.schema_migrations (
                    filename text PRIMARY KEY,
                    sha256 text NOT NULL,
                    applied_at timestamptz NOT NULL DEFAULT timezone('utc', now())
                );
                """
            )
            conn.commit()

        files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for sql_file in files:
            sql_text = sql_file.read_text(encoding="utf-8")
            digest = hashlib.sha256(sql_text.encode("utf-8")).hexdigest()
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT sha256 FROM app.schema_migrations WHERE filename = %s",
                    (sql_file.name,),
                )
                row = cur.fetchone()
                if row is not None:
                    if row[0] != digest:
                        raise RuntimeError(
                            f"Migration {sql_file.name} ja aplicada com checksum diferente!"
                        )
                    continue
                cur.execute(sql_text)
                cur.execute(
                    "INSERT INTO app.schema_migrations (filename, sha256) VALUES (%s, %s)",
                    (sql_file.name, digest),
                )
                conn.commit()
                applied.append(sql_file.name)
    return applied


if __name__ == "__main__":
    newly_applied = apply_all()
    print("applied_migrations=", newly_applied)
