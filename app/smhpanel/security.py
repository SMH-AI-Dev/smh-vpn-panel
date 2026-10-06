"""Password hashing, session tokens, CSRF and rate limiting."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

SESSION_COOKIE = "smhpanel_session"
CSRF_HEADER = "x-csrf-token"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


def create_session_token(
    secret: str, admin_id: int, username: str, csrf: str, ttl_hours: int = 24
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(admin_id),
        "username": username,
        "csrf": csrf,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=ttl_hours)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_session_token(secret: str, token: str) -> dict | None:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


class RateLimiter:
    """Fixed-window per-key failure limiter (in-memory)."""

    def __init__(self, max_failures: int = 10, window_seconds: int = 600):
        self.max_failures = max_failures
        self.window = window_seconds
        self._state: dict[str, tuple[int, float]] = {}

    def _now(self) -> float:
        return time.monotonic()

    def allowed(self, key: str) -> bool:
        count, start = self._state.get(key, (0, 0.0))
        if self._now() - start > self.window:
            return True
        return count < self.max_failures

    def failure(self, key: str) -> None:
        count, start = self._state.get(key, (0, self._now()))
        if self._now() - start > self.window:
            count, start = 0, self._now()
        self._state[key] = (count + 1, start)

    def clear(self, key: str) -> None:
        self._state.pop(key, None)
