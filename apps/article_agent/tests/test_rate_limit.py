import math
import unittest

from apps.article_agent.infrastructure.rate_limit import (
    QuotaLimit, RateLimitExceeded, RateLimitPolicy, RedisGroqLimiter,
)


class FakeRedis:
    """Small semantic emulator for the limiter's atomic Lua contract."""

    def __init__(self):
        self.counters = {}
        self.active = {}

    def _counter(self, key, now):
        value, expiry = self.counters.get(key, (0, now))
        return (0, now) if expiry <= now else (value, expiry)

    async def eval(self, _script, key_count, *args):
        keys, values = args[:key_count], args[key_count:]
        if key_count == 10:
            now, lease, reservation_id, input_tokens, output_tokens, window, *limits = values
            for key in (keys[0], keys[5]):
                self.active.setdefault(key, {})
                self.active[key] = {
                    item: expiry for item, expiry in self.active[key].items() if expiry > now
                }
            amounts = [None, 1, input_tokens + output_tokens, input_tokens, output_tokens]
            for index, limit in enumerate(limits, start=1):
                if not limit:
                    continue
                key = keys[index - 1]
                if index in {1, 6}:
                    if len(self.active[key]) >= limit:
                        return [0, index, max(1, math.ceil(min(self.active[key].values()) - now))]
                else:
                    current, expiry = self._counter(key, now)
                    amount = amounts[(index - 1) % 5]
                    if current + amount > limit:
                        return [0, index, max(1, math.ceil(expiry - now))]
            for index, limit in enumerate(limits, start=1):
                if not limit:
                    continue
                key = keys[index - 1]
                if index in {1, 6}:
                    self.active[key][reservation_id] = now + lease
                else:
                    current, expiry = self._counter(key, now)
                    amount = amounts[(index - 1) % 5]
                    self.counters[key] = (current + amount, expiry if current else now + window)
            return [1, 0, 0]
        if key_count == 2:
            reservation_id = values[0]
            for key in keys:
                self.active.setdefault(key, {}).pop(reservation_id, None)
            return 1
        if key_count == 8:
            reservation_id, combined, input_delta, output_delta = values
            for key in keys[:2]:
                self.active.setdefault(key, {}).pop(reservation_id, None)
            for key, delta in zip(keys[2:], (combined, input_delta, output_delta) * 2, strict=True):
                current, expiry = self.counters.get(key, (0, 0))
                self.counters[key] = (max(0, current - delta), expiry)
            return 1
        raise AssertionError(f"unexpected Lua key count: {key_count}")

    async def aclose(self):
        pass


class RedisGroqLimiterTests(unittest.IsolatedAsyncioTestCase):
    def limiter(self, backend, *, account, model_limits=None):
        return RedisGroqLimiter(
            backend,
            RateLimitPolicy(account=account, model_limits=model_limits or {}, key_prefix="test", lease_seconds=15),
        )

    async def test_shared_backend_rejects_concurrency_with_its_own_retry_time(self):
        backend = FakeRedis()
        account = QuotaLimit(concurrency=1, requests_per_window=10, tokens_per_window=1000)
        first, second = self.limiter(backend, account=account), self.limiter(backend, account=account)
        reservation = await first.reserve(10, 10, model="primary")
        with self.assertRaisesRegex(RateLimitExceeded, "account_concurrency") as raised:
            await second.reserve(10, 10, model="primary")
        self.assertLessEqual(raised.exception.retry_after, 15)
        await first.release(reservation)
        await second.reserve(10, 10, model="primary")

    async def test_token_quota_is_not_consumed_by_unused_completion_capacity(self):
        backend = FakeRedis()
        account = QuotaLimit(concurrency=2, requests_per_window=10, tokens_per_window=120)
        limiter = self.limiter(backend, account=account)
        first = await limiter.reserve(20, 80, model="primary")
        await limiter.settle(first, actual_input_tokens=18, actual_output_tokens=12)
        # The first request consumed 30, not its pessimistic reservation of 100.
        second = await limiter.reserve(20, 60, model="primary")
        await limiter.release(second)

    async def test_usage_higher_than_estimate_is_recorded_not_silently_discarded(self):
        backend = FakeRedis()
        account = QuotaLimit(concurrency=2, requests_per_window=10, tokens_per_window=100)
        limiter = self.limiter(backend, account=account)
        first = await limiter.reserve(10, 20, model="primary")
        await limiter.settle(first, actual_input_tokens=20, actual_output_tokens=35)
        with self.assertRaisesRegex(RateLimitExceeded, "account_tokens"):
            await limiter.reserve(30, 20, model="primary")

    async def test_model_quota_blocks_fallback_model_without_blocking_other_model(self):
        backend = FakeRedis()
        account = QuotaLimit(concurrency=3, requests_per_window=10, tokens_per_window=1_000)
        models = {"limited": QuotaLimit(concurrency=2, requests_per_window=1, tokens_per_window=100)}
        limiter = self.limiter(backend, account=account, model_limits=models)
        first = await limiter.reserve(10, 20, model="limited")
        with self.assertRaisesRegex(RateLimitExceeded, "model_requests"):
            await limiter.reserve(10, 20, model="limited")
        other = await limiter.reserve(10, 20, model="other")
        await limiter.release(first)
        await limiter.release(other)
