from __future__ import annotations

from apps.api.config import get_settings
from adapters.supabase_db.client import SupabaseRestClient


def main() -> int:
    settings = get_settings()
    client = SupabaseRestClient(
        supabase_url=settings.next_public_supabase_url,
        publishable_key=settings.next_public_supabase_publishable_key,
    )
    ok = client.check_health()
    print(f"supabase_reachable={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
