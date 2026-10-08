"""Redis-backed, cross-worker Groq request and concurrency coordination."""

from __future__ import annotations

import math
from dataclasses import dataclass

from redis.asyncio import Redis


class RateLimitExceeded(RuntimeError):
    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"rate limit reservation unavailable; retry-after: {retry_after}")


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    concurrency: int = 4
    requests_per_window: int = 30
    tokens_per_window: int = 30_000
    window_seconds: int = 60
    key_prefix: str = "article-agent:groq"


class RedisGroqLimiter:
    _reserve_script = """
local active = tonumber(redis.call('GET', KEYS[1]) or '0')
local requests = tonumber(redis.call('GET', KEYS[2]) or '0')
local tokens = tonumber(redis.call('GET', KEYS[3]) or '0')
if active >= tonumber(ARGV[1]) or requests >= tonumber(ARGV[2]) or tokens + tonumber(ARGV[3]) > tonumber(ARGV[4]) then
  return {0, math.max(redis.call('TTL', KEYS[2]), 1)}
end
redis.call('INCR', KEYS[1]); redis.call('EXPIRE', KEYS[1], ARGV[5])
redis.call('INCR', KEYS[2]); redis.call('EXPIRE', KEYS[2], ARGV[5])
redis.call('INCRBY', KEYS[3], ARGV[3]); redis.call('EXPIRE', KEYS[3], ARGV[5])
return {1, 0}
"""
    _release_script = """
local active = tonumber(redis.call('GET', KEYS[1]) or '0')
if active > 0 then redis.call('DECR', KEYS[1]) end
return 1
"""

    def __init__(self, redis: Redis, policy: RateLimitPolicy | None = None) -> None:
        self.redis, self.policy = redis, policy or RateLimitPolicy()

    @classmethod
    def from_url(cls, url: str, policy: RateLimitPolicy | None = None) -> "RedisGroqLimiter":
        return cls(Redis.from_url(url, decode_responses=True), policy)

    async def reserve(self, estimated_tokens: int) -> None:
        policy = self.policy
        keys = [f"{policy.key_prefix}:active", f"{policy.key_prefix}:requests", f"{policy.key_prefix}:tokens"]
        result = await self.redis.eval(
            self._reserve_script, len(keys), *keys, policy.concurrency, policy.requests_per_window,
            max(1, estimated_tokens), policy.tokens_per_window, policy.window_seconds,
        )
        allowed, retry_after = int(result[0]), int(result[1])
        if not allowed:
            raise RateLimitExceeded(max(1, retry_after))

    async def release(self) -> None:
        await self.redis.eval(self._release_script, 1, f"{self.policy.key_prefix}:active")

    async def close(self) -> None:
        await self.redis.aclose()
