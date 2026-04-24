"""Optional helper to seed Redis with some demo preferences (for manual CLI play)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from datetime import datetime

from agent.config import get_settings  # noqa: E402
from agent.memory.redis_store import RedisMemory  # noqa: E402
from agent.schemas.memory import Preference  # noqa: E402


def main() -> int:
    s = get_settings()
    redis = RedisMemory(
        url=s.redis_url,
        key_prefix=s.memory.redis.key_prefix,
        fact_default_ttl_days=s.memory.redis.fact_default_ttl_days,
        use_fake=s.use_fake_redis,
    )
    user = s.user.default_user_id
    redis.clear_user(user)
    redis.write(Preference(user_id=user, key="language.liked", value="python", confidence=0.95,
                           updated_at=datetime.utcnow()))
    redis.write(Preference(user_id=user, key="language.disliked", value="java", confidence=0.9,
                           updated_at=datetime.utcnow()))
    print(f"Seeded preferences for user={user}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
