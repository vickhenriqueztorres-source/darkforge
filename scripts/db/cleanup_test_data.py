from __future__ import annotations

import os
import psycopg
from dotenv import load_dotenv

load_dotenv()


def cleanup() -> int:
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        res = conn.execute(
            """
            DELETE FROM public.workspaces
            WHERE slug LIKE 'sp03-%'
               OR slug LIKE 'sp02-%'
               OR slug LIKE 'ws-a-%'
               OR slug LIKE 'ws-b-%'
            """
        )
        conn.commit()
        return res.rowcount or 0


if __name__ == "__main__":
    print("deleted_test_workspaces=", cleanup())
