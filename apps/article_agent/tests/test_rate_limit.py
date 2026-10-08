import unittest

from apps.article_agent.infrastructure.rate_limit import RateLimitExceeded, RateLimitPolicy, RedisGroqLimiter


class FakeRedis:
    def __init__(self): self.active = 0
    async def eval(self, script, key_count, *args):
        if key_count == 1:
            self.active = max(0, self.active - 1)
            return 1
        concurrency = int(args[3])
        if self.active >= concurrency:
            return [0, 7]
        self.active += 1
        return [1, 0]
    async def aclose(self): pass


class RedisGroqLimiterTests(unittest.IsolatedAsyncioTestCase):
    async def test_shared_backend_rejects_concurrent_reservation_and_returns_retry_after(self):
        backend = FakeRedis()
        policy = RateLimitPolicy(concurrency=1, key_prefix="test")
        first, second = RedisGroqLimiter(backend, policy), RedisGroqLimiter(backend, policy)
        await first.reserve(10)
        with self.assertRaisesRegex(RateLimitExceeded, "retry-after: 7"):
            await second.reserve(10)
        await first.release()
        await second.reserve(10)
