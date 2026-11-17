"""Daemon local do worker de agentes do Studio UI (executa jobs agent.execute da fila Postgres)."""
from __future__ import annotations

import logging
import os
import signal
import time
from uuid import uuid4

from dotenv import load_dotenv

from adapters.supabase_db.jobs_repo import PostgresWorkerQueue
from adapters.supabase_db.studio_repo import PostgresStudioRepository
from apps.api.config import get_settings
from apps.api.dependencies import build_default_container
from workers.agents.handler import AgentJobHandler
from workers.runner import JobWorker
from workers.sync.handler import build_youtube_sync_handler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("darkforge.agent_daemon")


def main() -> None:
    load_dotenv()
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL nao configurada no .env")

    worker_id = f"studio-agent-worker-{uuid4().hex[:8]}"
    repo = PostgresStudioRepository(db_url)
    queue = PostgresWorkerQueue(db_url)
    handler = AgentJobHandler(repo, step_delay_seconds=1.1)
    handlers: dict[str, object] = {"agent.execute": handler}
    job_types = ["agent.execute"]
    container = build_default_container(get_settings())
    if container.analytics is not None:
        handlers["youtube.channel_sync"] = build_youtube_sync_handler(container.analytics)
        job_types.append("youtube.channel_sync")
    worker = JobWorker(
        queue,
        worker_id=worker_id,
        handlers=handlers,  # type: ignore[arg-type]
        lease_seconds=45,
    )

    running = True

    def _stop(_sig: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    logger.info("Worker de agentes iniciado (%s). Aguardando jobs agent.execute...", worker_id)
    last_reconcile = 0.0
    while running:
        try:
            now = time.monotonic()
            if now - last_reconcile > 15.0:
                reconciled = repo.reconcile_expired_agent_runs()
                if reconciled:
                    logger.info("Reconciliados %d runs expirados", reconciled)
                last_reconcile = now

            job_id = worker.run_once(job_types=job_types)
            if job_id is not None:
                logger.info("Job agent.execute processado: %s", job_id)
                continue
        except Exception as exc:
            logger.warning("Erro no ciclo do worker: %s", exc)
        time.sleep(1.0)

    logger.info("Worker de agentes encerrado.")


if __name__ == "__main__":
    main()
