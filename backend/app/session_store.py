import json
import threading
from typing import Any, Dict

from .config import REDIS_URL, USE_REDIS, RATE_LIMIT_PER_MIN, PERSONA_DEFAULT


def new_session() -> Dict[str, Any]:
    return {
        "history": [],
        "intel": {"upi_ids": [], "bank_accounts": [], "phishing_links": []},
        "scam_detected": False,
        "agent_active": False,
        "persona": PERSONA_DEFAULT,
        "persona_profile": {},
        "asked_fields": [],
    }


class InMemorySessionStore:
    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get_session(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            if session_id not in self._store:
                self._store[session_id] = new_session()
            return self._store[session_id]

    def save_session(self, session_id: str, session: Dict[str, Any]) -> None:
        with self._lock:
            self._store[session_id] = session


class RedisSessionStore:
    def __init__(self, redis_url: str) -> None:
        import redis

        self.client = redis.Redis.from_url(redis_url, decode_responses=True)

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def get_session(self, session_id: str) -> Dict[str, Any]:
        data = self.client.get(self._key(session_id))
        if not data:
            return new_session()
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return new_session()

    def save_session(self, session_id: str, session: Dict[str, Any]) -> None:
        self.client.set(self._key(session_id), json.dumps(session))


class RateLimiter:
    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute

    def allow(self, key: str) -> bool:
        # Stub for hackathon: always allow. Replace with Redis token bucket.
        return True


def get_session_store():
    if USE_REDIS and REDIS_URL:
        try:
            return RedisSessionStore(REDIS_URL)
        except Exception:
            return InMemorySessionStore()
    return InMemorySessionStore()


def get_rate_limiter() -> RateLimiter:
    return RateLimiter(RATE_LIMIT_PER_MIN)
