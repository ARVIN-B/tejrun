import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from django.test import SimpleTestCase, override_settings

from apps.article_agent.infrastructure.ai.groq_client import GroqClient, ProviderRateLimitError
from apps.article_agent.infrastructure.rate_limit import RateLimitExceeded, Reservation


class FakeLimiter:
    def __init__(self, outcomes=()):
        self.outcomes = list(outcomes)
        self.reservations = []
        self.settled = []
        self.released = []

    async def reserve(self, input_tokens, output_tokens, *, model):
        if self.outcomes:
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
        reservation = Reservation(str(len(self.reservations)), model, input_tokens, output_tokens)
        self.reservations.append(reservation)
        return reservation

    async def settle(self, reservation, *, actual_input_tokens, actual_output_tokens):
        reservation.released = reservation.settled = True
        self.settled.append((reservation, actual_input_tokens, actual_output_tokens))

    async def release(self, reservation):
        reservation.released = True
        self.released.append(reservation)

    async def close(self):
        pass


class FakeModelClient:
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error
        self.calls = []
        self.closed = False

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.result

    async def close(self):
        self.closed = True


def response(text="ok", prompt_tokens=10, completion_tokens=5):
    return SimpleNamespace(
        content=text,
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


class Http429(RuntimeError):
    status_code = 429
    headers = {"retry-after": "7"}


class Http503(RuntimeError):
    status_code = 503


class GroqClientConfigurationTests(SimpleTestCase):
    @override_settings(ARTICLE_AGENT_LLM_MAX_OUTPUT_TOKENS=4096)
    @patch("apps.article_agent.infrastructure.ai.groq_client.RedisGroqLimiter.from_url")
    @patch("apps.article_agent.infrastructure.ai.groq_client.OpenAIChatCompletionClient")
    def test_constructs_primary_client_with_configured_ceiling(self, model_client, limiter_factory) -> None:
        client = GroqClient()
        client._client_for(client.route.primary)
        self.assertEqual(model_client.call_args.kwargs["max_tokens"], 4096)
        limiter_factory.assert_called_once()

    @override_settings(
        ARTICLE_AGENT_PRIMARY_MODEL="primary", ARTICLE_AGENT_FALLBACK_MODELS=("fallback",),
        ARTICLE_AGENT_REVIEW_MODEL="fallback",
    )
    def test_review_model_is_used_only_when_explicitly_configured(self) -> None:
        client = GroqClient()
        self.assertEqual(client.route.candidates("section_write"), ("primary", "fallback"))
        self.assertEqual(client.route.candidates("section_review"), ("fallback", "primary"))

    def test_invalid_model_quota_configuration_is_rejected(self) -> None:
        with self.settings(ARTICLE_AGENT_GROQ_MODEL_LIMITS={"primary": {"bad": 1}}):
            with self.assertRaisesRegex(ValueError, "Unsupported model quota"):
                GroqClient()


class GroqClientGenerationTests(SimpleTestCase):
    def make_client(self, *, limiter, clients):
        client = GroqClient()
        client.limiter = limiter
        client._model_clients = clients
        return client

    def test_small_actual_response_settles_large_operation_reservation(self) -> None:
        limiter = FakeLimiter()
        model = FakeModelClient(response(prompt_tokens=12, completion_tokens=8))
        client = self.make_client(limiter=limiter, clients={"openai/gpt-oss-120b": model})
        result = asyncio.run(client.generate("a prompt", operation="section_write", output_tokens=2000))
        self.assertEqual(result, "ok")
        self.assertEqual(limiter.reservations[0].output_tokens, 2000)
        self.assertEqual(limiter.settled[0][1:], (12, 8))
        self.assertEqual(model.calls[0]["extra_create_args"]["max_tokens"], 2000)

    @override_settings(ARTICLE_AGENT_PRIMARY_MODEL="primary", ARTICLE_AGENT_FALLBACK_MODELS=("fallback",))
    def test_model_quota_rejection_uses_configured_fallback_once(self) -> None:
        limiter = FakeLimiter([RateLimitExceeded("model_tokens", 4)])
        fallback = FakeModelClient(response())
        client = self.make_client(limiter=limiter, clients={"fallback": fallback})
        self.assertEqual(asyncio.run(client.generate("prompt")), "ok")
        self.assertEqual([item.model for item in limiter.reservations], ["fallback"])

    def test_provider_429_is_distinct_from_local_rate_limit(self) -> None:
        limiter = FakeLimiter()
        model = FakeModelClient(error=Http429("quota"))
        client = self.make_client(limiter=limiter, clients={"openai/gpt-oss-120b": model})
        with self.assertRaises(ProviderRateLimitError) as raised:
            asyncio.run(client.generate("prompt"))
        self.assertEqual(raised.exception.retry_after, 7)
        self.assertEqual(len(limiter.released), 1)

    def test_timeout_is_normalized_and_releases_the_active_slot(self) -> None:
        limiter = FakeLimiter()
        model = FakeModelClient(error=TimeoutError("provider timed out"))
        client = self.make_client(limiter=limiter, clients={"openai/gpt-oss-120b": model})
        from apps.article_agent.infrastructure.ai.groq_client import ProviderTransientError

        with self.assertRaises(ProviderTransientError):
            asyncio.run(client.generate("prompt"))
        self.assertEqual(len(limiter.released), 1)

    def test_provider_5xx_is_normalized_and_releases_the_active_slot(self) -> None:
        limiter = FakeLimiter()
        model = FakeModelClient(error=Http503("temporary capacity"))
        client = self.make_client(limiter=limiter, clients={"openai/gpt-oss-120b": model})
        from apps.article_agent.infrastructure.ai.groq_client import ProviderTransientError

        with self.assertRaises(ProviderTransientError):
            asyncio.run(client.generate("prompt"))
        self.assertEqual(len(limiter.released), 1)

    @override_settings(ARTICLE_AGENT_PRIMARY_MODEL="primary", ARTICLE_AGENT_FALLBACK_MODELS=("fallback",))
    def test_fallback_stops_after_each_candidate_is_rate_limited(self) -> None:
        limiter = FakeLimiter([
            RateLimitExceeded("model_tokens", 4), RateLimitExceeded("model_tokens", 5),
        ])
        client = self.make_client(limiter=limiter, clients={})
        with self.assertRaises(RateLimitExceeded):
            asyncio.run(client.generate("prompt"))
        self.assertFalse(limiter.reservations)

    def test_cancellation_releases_only_the_active_slot(self) -> None:
        limiter = FakeLimiter()

        class CancellingClient(FakeModelClient):
            async def create(self, **kwargs):
                raise asyncio.CancelledError()

        client = self.make_client(
            limiter=limiter, clients={"openai/gpt-oss-120b": CancellingClient()},
        )
        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(client.generate("prompt"))
        self.assertEqual(len(limiter.released), 1)
        self.assertFalse(limiter.settled)
