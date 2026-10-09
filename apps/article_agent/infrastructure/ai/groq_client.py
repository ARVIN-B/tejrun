import asyncio
import os
import math

from django.conf import settings
from apps.article_agent.infrastructure.rate_limit import RateLimitPolicy, RedisGroqLimiter

from autogen_core import CancellationToken
from autogen_core.models import UserMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient


class GroqClient:
    def __init__(self):
        self.model_client = OpenAIChatCompletionClient(
            model=os.getenv("LLM_MODEL"),
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL"),
            model_info={
                "vision": False,
                "function_calling": False,
                "json_output": False,
                "family": "unknown",
                "structured_output": False,
            },
            # Providers often default to a short completion limit. The
            # ArticleBudget can require substantially more prose per unit.
            max_tokens=settings.ARTICLE_AGENT_LLM_MAX_OUTPUT_TOKENS,
        )
        self.limiter = RedisGroqLimiter.from_url(
            settings.REDIS_URL,
            RateLimitPolicy(concurrency=settings.ARTICLE_AGENT_GROQ_CONCURRENCY,
                            requests_per_window=settings.ARTICLE_AGENT_GROQ_REQUESTS_PER_MINUTE,
                            tokens_per_window=settings.ARTICLE_AGENT_GROQ_TOKENS_PER_MINUTE),
        )

    async def generate(self, prompt: str) -> str:
        # Reserve both prompt and configured completion capacity, because the
        # latter is the portion that caused short provider output in practice.
        await self.limiter.reserve(
            max(1, math.ceil(len(prompt) / 4)) + settings.ARTICLE_AGENT_LLM_MAX_OUTPUT_TOKENS
        )
        try:
            result = await asyncio.wait_for(
                self.model_client.create(
                    messages=[UserMessage(content=prompt, source="user")],
                    cancellation_token=CancellationToken(),
                ), timeout=settings.ARTICLE_AGENT_LLM_TIMEOUT_SECONDS,
            )
            return result.content
        finally:
            await self.limiter.release()

    async def close(self):
        await self.model_client.close()
        await self.limiter.close()
