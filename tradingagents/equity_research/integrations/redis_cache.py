"""Redis helpers for rate limiting, budget counters, and semantic cache."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import redis


def get_redis_url(config: dict[str, Any] | None = None) -> str:
    if config and config.get("redis_url"):
        return config["redis_url"]
    return os.environ.get("TRADINGAGENTS_REDIS_URL", "redis://localhost:6379/0")


class RedisClient:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._client: redis.Redis | None = None
        self._memory: dict[str, int | str] = {}
        self._use_memory = bool(self.config.get("equity_research_use_memory"))

    @property
    def client(self) -> redis.Redis:
        if self._use_memory:
            raise RuntimeError("memory mode")
        if self._client is None:
            self._client = redis.from_url(get_redis_url(self.config), decode_responses=True)
        return self._client

    def rate_limit(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        if self._use_memory:
            return True
        try:
            rkey = f"rate:{key}"
            count = self.client.incr(rkey)
            if count == 1:
                self.client.expire(rkey, window_seconds)
            return count <= limit
        except Exception:
            return True

    def budget_decr(self, report_id: str, resource: str) -> int:
        rkey = f"budget:{report_id}:{resource}"
        if self._use_memory:
            val = int(self._memory.get(rkey, 0)) - 1
            self._memory[rkey] = val
            return max(0, val)
        try:
            val = self.client.decr(rkey)
            if val == -1:
                self.client.set(rkey, 0)
                return 0
            return val
        except Exception:
            return 0

    def budget_init(self, report_id: str, budgets: dict[str, int]) -> None:
        for resource, amount in budgets.items():
            rkey = f"budget:{report_id}:{resource}"
            if self._use_memory:
                self._memory[rkey] = amount
            else:
                try:
                    self.client.set(rkey, amount)
                except Exception:
                    self._memory[rkey] = amount

    def budget_get(self, report_id: str, resource: str) -> int:
        rkey = f"budget:{report_id}:{resource}"
        if self._use_memory:
            return int(self._memory.get(rkey, 0))
        try:
            val = self.client.get(rkey)
            return int(val) if val is not None else 0
        except Exception:
            return int(self._memory.get(rkey, 0))

    def semantic_cache_get(self, key: str) -> dict[str, Any] | None:
        if self._use_memory:
            raw = self._memory.get(f"semcache:{key}")
            return json.loads(raw) if isinstance(raw, str) else None
        try:
            raw = self.client.get(f"semcache:{key}")
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def semantic_cache_set(self, key: str, value: dict[str, Any], ttl: int = 900) -> None:
        if self._use_memory:
            self._memory[f"semcache:{key}"] = json.dumps(value)
            return
        try:
            self.client.setex(f"semcache:{key}", ttl, json.dumps(value))
        except Exception:
            self._memory[f"semcache:{key}"] = json.dumps(value)

    @staticmethod
    def cache_key(*parts: str) -> str:
        raw = ":".join(parts)
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
