import asyncio
import os

from django.conf import settings

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
        )

    async def generate(self, prompt: str) -> str:
        result = await asyncio.wait_for(
            self.model_client.create(
                messages=[
                    UserMessage(
                        content=prompt,
                        source="user",
                    )
                ],
                cancellation_token=CancellationToken(),
            ),
            timeout=settings.ARTICLE_AGENT_LLM_TIMEOUT_SECONDS,
        )

        return result.content

    async def close(self):
        await self.model_client.close()
