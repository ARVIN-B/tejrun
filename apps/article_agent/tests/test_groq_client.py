from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.article_agent.infrastructure.ai.groq_client import GroqClient


class GroqClientConfigurationTests(SimpleTestCase):
    @override_settings(ARTICLE_AGENT_LLM_MAX_OUTPUT_TOKENS=4096)
    @patch("apps.article_agent.infrastructure.ai.groq_client.RedisGroqLimiter.from_url")
    @patch("apps.article_agent.infrastructure.ai.groq_client.OpenAIChatCompletionClient")
    def test_configures_a_completion_limit_large_enough_for_budgeted_prose(
        self, model_client, limiter_factory
    ) -> None:
        """Never silently use a provider's short default completion limit."""
        GroqClient()

        self.assertEqual(model_client.call_args.kwargs["max_tokens"], 4096)
        limiter_factory.assert_called_once()
