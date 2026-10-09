"""Atomic, model-aware Redis quotas for provider calls.

The limiter deliberately distinguishes a local reservation from an HTTP 429.
Reservations are conservative until a successful provider response supplies
actual usage; concurrency slots are always released, while unknown failed
requests retain their token reservation for the current window.
"""

from __future__ import annotations

import hashlib
import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

from redis.asyncio import Redis


LimitCause = Literal[
    "account_concurrency", "account_requests", "account_tokens",
    "account_input_tokens", "account_output_tokens", "model_concurrency",
    "model_requests", "model_tokens", "model_input_tokens", "model_output_tokens",
]


class RateLimitExceeded(RuntimeError):
    """A local Redis quota prevented sending a request to the provider."""

    def __init__(self, cause: LimitCause, retry_after: int) -> None:
        self.cause, self.retry_after = cause, max(1, retry_after)
        super().__init__(
            f"local_rate_limit:{cause}; retry-after: {self.retry_after}"
        )


class ReservationTooLarge(RuntimeError):
    """The requested operation can never fit a configured quota window."""


@dataclass(frozen=True, slots=True)
class QuotaLimit:
    """A quota scope; ``None`` disables an individual dimension."""

    concurrency: int | None = None
    requests_per_window: int | None = None
    tokens_per_window: int | None = None
    input_tokens_per_window: int | None = None
    output_tokens_per_window: int | None = None

    def __post_init__(self) -> None:
        for value in (
            self.concurrency, self.requests_per_window, self.tokens_per_window,
            self.input_tokens_per_window, self.output_tokens_per_window,
        ):
            if value is not None and value <= 0:
                raise ValueError("Configured quota values must be positive.")

    def with_margin(self, margin: float) -> "QuotaLimit":
        def adjusted(value: int | None) -> int | None:
            return None if value is None else max(1, math.floor(value * margin))

        return QuotaLimit(
            concurrency=self.concurrency,
            requests_per_window=adjusted(self.requests_per_window),
            tokens_per_window=adjusted(self.tokens_per_window),
            input_tokens_per_window=adjusted(self.input_tokens_per_window),
            output_tokens_per_window=adjusted(self.output_tokens_per_window),
        )


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    """Account-wide and optional per-model quotas.

    Account limits always apply. A model limit is additive, never a substitute
    for account limits, because changing models does not generally bypass an
    organization or project quota.
    """

    account: QuotaLimit = field(
        default_factory=lambda: QuotaLimit(
            concurrency=4, requests_per_window=30, tokens_per_window=30_000,
        )
    )
    model_limits: dict[str, QuotaLimit] = field(default_factory=dict)
    window_seconds: int = 60
    lease_seconds: int = 150
    key_prefix: str = "article-agent:groq"

    def __post_init__(self) -> None:
        if self.window_seconds <= 0 or self.lease_seconds <= 0:
            raise ValueError("Rate-limit window and lease must be positive.")

    def model_limit_for(self, model: str) -> QuotaLimit:
        return self.model_limits.get(model, QuotaLimit())


@dataclass(slots=True)
class Reservation:
    identifier: str
    model: str
    input_tokens: int
    output_tokens: int
    released: bool = False
    settled: bool = False


_CAUSES: tuple[LimitCause, ...] = (
    "account_concurrency", "account_requests", "account_tokens",
    "account_input_tokens", "account_output_tokens", "model_concurrency",
    "model_requests", "model_tokens", "model_input_tokens", "model_output_tokens",
)


class RedisGroqLimiter:
    """Coordinates account and model quotas across all Celery workers."""

    _reserve_script = """
local now = tonumber(ARGV[1])
local lease = tonumber(ARGV[2])
local reservation_id = ARGV[3]
local input_tokens = tonumber(ARGV[4])
local output_tokens = tonumber(ARGV[5])
local window = tonumber(ARGV[6])

local function ttl_or_window(key)
  local ttl = redis.call('TTL', key)
  if ttl == nil or ttl < 1 then return window end
  return ttl
end

local function active_retry(key, limit)
  if limit == 0 then return 0 end
  redis.call('ZREMRANGEBYSCORE', key, '-inf', now)
  if redis.call('ZCARD', key) < limit then return 0 end
  local item = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  if item[2] == nil then return 1 end
  return math.max(1, math.ceil(tonumber(item[2]) - now))
end

local function counter_retry(key, amount, limit)
  if limit == 0 then return 0 end
  local current = tonumber(redis.call('GET', key) or '0')
  if current + amount <= limit then return 0 end
  return ttl_or_window(key)
end

-- Limits are account concurrency/RPM/TPM/ITPM/OTPM, then model equivalents.
for index = 1, 10 do
  local limit = tonumber(ARGV[6 + index])
  local amount = 0
  if index == 1 or index == 6 then
    local retry = active_retry(KEYS[index == 1 and 1 or 6], limit)
    if retry > 0 then return {0, index, retry} end
  else
    if index == 2 or index == 7 then amount = 1
    elseif index == 3 or index == 8 then amount = input_tokens + output_tokens
    elseif index == 4 or index == 9 then amount = input_tokens
    else amount = output_tokens end
    local key_offset = index <= 5 and index or index
    local retry = counter_retry(KEYS[key_offset], amount, limit)
    if retry > 0 then return {0, index, retry} end
  end
end

local function add_counter(key, amount, limit)
  if limit == 0 then return end
  if redis.call('EXISTS', key) == 0 then
    redis.call('SET', key, amount, 'EX', window)
  else
    redis.call('INCRBY', key, amount)
  end
end

for index = 1, 10 do
  local limit = tonumber(ARGV[6 + index])
  if index == 1 or index == 6 then
    if limit > 0 then
      local key = KEYS[index == 1 and 1 or 6]
      redis.call('ZADD', key, now + lease, reservation_id)
      local current_ttl = redis.call('TTL', key)
      if current_ttl == nil or current_ttl < math.ceil(lease) then
        redis.call('EXPIRE', key, math.ceil(lease))
      end
    end
  else
    local amount = 0
    if index == 2 or index == 7 then amount = 1
    elseif index == 3 or index == 8 then amount = input_tokens + output_tokens
    elseif index == 4 or index == 9 then amount = input_tokens
    else amount = output_tokens end
    add_counter(KEYS[index], amount, limit)
  end
end
return {1, 0, 0}
"""

    _release_script = """
redis.call('ZREM', KEYS[1], ARGV[1])
redis.call('ZREM', KEYS[2], ARGV[1])
return 1
"""

    _settle_script = """
local function reconcile(key, amount)
  if redis.call('EXISTS', key) == 0 then return end
  local current = tonumber(redis.call('GET', key) or '0')
  if amount >= 0 then
    redis.call('SET', key, math.max(0, current - amount), 'KEEPTTL')
  else
    redis.call('INCRBY', key, -amount)
  end
end
redis.call('ZREM', KEYS[1], ARGV[1])
redis.call('ZREM', KEYS[2], ARGV[1])
reconcile(KEYS[3], tonumber(ARGV[2]))
reconcile(KEYS[4], tonumber(ARGV[3]))
reconcile(KEYS[5], tonumber(ARGV[4]))
reconcile(KEYS[6], tonumber(ARGV[2]))
reconcile(KEYS[7], tonumber(ARGV[3]))
reconcile(KEYS[8], tonumber(ARGV[4]))
return 1
"""

    def __init__(self, redis: Redis, policy: RateLimitPolicy | None = None) -> None:
        self.redis, self.policy = redis, policy or RateLimitPolicy()

    @classmethod
    def from_url(cls, url: str, policy: RateLimitPolicy | None = None) -> "RedisGroqLimiter":
        return cls(Redis.from_url(url, decode_responses=True), policy)

    def _keys(self, model: str) -> list[str]:
        model_key = hashlib.sha256(model.encode("utf-8")).hexdigest()[:16]
        account = f"{self.policy.key_prefix}:account"
        model_prefix = f"{self.policy.key_prefix}:model:{model_key}"
        return [
            f"{account}:active", f"{account}:requests", f"{account}:tokens",
            f"{account}:input_tokens", f"{account}:output_tokens",
            f"{model_prefix}:active", f"{model_prefix}:requests", f"{model_prefix}:tokens",
            f"{model_prefix}:input_tokens", f"{model_prefix}:output_tokens",
        ]

    @staticmethod
    def _limits(quota: QuotaLimit) -> list[int]:
        return [
            quota.concurrency or 0, quota.requests_per_window or 0,
            quota.tokens_per_window or 0, quota.input_tokens_per_window or 0,
            quota.output_tokens_per_window or 0,
        ]

    def _preflight(self, input_tokens: int, output_tokens: int, model: str) -> None:
        for scope, quota in (("account", self.policy.account), ("model", self.policy.model_limit_for(model))):
            if quota.tokens_per_window and input_tokens + output_tokens > quota.tokens_per_window:
                raise ReservationTooLarge(f"{scope}_combined_token_reservation_exceeds_window")
            if quota.input_tokens_per_window and input_tokens > quota.input_tokens_per_window:
                raise ReservationTooLarge(f"{scope}_input_token_reservation_exceeds_window")
            if quota.output_tokens_per_window and output_tokens > quota.output_tokens_per_window:
                raise ReservationTooLarge(f"{scope}_output_token_reservation_exceeds_window")

    async def reserve(self, input_tokens: int, output_tokens: int, *, model: str) -> Reservation:
        input_tokens, output_tokens = max(1, input_tokens), max(1, output_tokens)
        self._preflight(input_tokens, output_tokens, model)
        reservation = Reservation(str(uuid.uuid4()), model, input_tokens, output_tokens)
        result = await self.redis.eval(
            self._reserve_script, 10, *self._keys(model), time.time(), self.policy.lease_seconds,
            reservation.identifier, input_tokens, output_tokens, self.policy.window_seconds,
            *self._limits(self.policy.account), *self._limits(self.policy.model_limit_for(model)),
        )
        allowed, cause, retry_after = (int(value) for value in result)
        if not allowed:
            raise RateLimitExceeded(_CAUSES[cause - 1], retry_after)
        return reservation

    async def release(self, reservation: Reservation) -> None:
        """Release concurrency only when no provider usage is known."""
        if reservation.released:
            return
        keys = self._keys(reservation.model)
        await self.redis.eval(self._release_script, 2, keys[0], keys[5], reservation.identifier)
        reservation.released = True

    async def settle(
        self, reservation: Reservation, *, actual_input_tokens: int, actual_output_tokens: int
    ) -> None:
        """Release slots and reconcile conservative capacity with real usage."""
        if reservation.settled:
            return
        input_delta = reservation.input_tokens - max(0, actual_input_tokens)
        output_delta = reservation.output_tokens - max(0, actual_output_tokens)
        combined_delta = input_delta + output_delta
        keys = self._keys(reservation.model)
        await self.redis.eval(
            self._settle_script, 8,
            keys[0], keys[5], keys[2], keys[3], keys[4], keys[7], keys[8], keys[9],
            reservation.identifier, combined_delta, input_delta, output_delta,
        )
        reservation.released = reservation.settled = True

    async def close(self) -> None:
        await self.redis.aclose()
