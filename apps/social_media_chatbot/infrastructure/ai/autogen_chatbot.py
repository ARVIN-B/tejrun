import os

from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient


class AutoGenChatbot:
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

        self.agent = AssistantAgent(
            name="social_media_assistant",
            model_client=self.model_client,
            system_message=(
                "You are a helpful social media assistant. "
                "You help users with social media related questions, "
                "content creation, captions, ideas, and communication."
            ),
        )

    async def chat(
        self,
        message: str,
        history=None,
    ) -> str:
        prompt_parts = []

        if history:
            prompt_parts.append("Here is the conversation history:")

            for item in history:
                role = "User" if item.role == "user" else "Assistant"

                prompt_parts.append(f"{role}: {item.content}")

        prompt_parts.append(f"User: {message}")

        prompt = "\n".join(prompt_parts)

        result = await self.agent.run(task=prompt)

        return result.messages[-1].content

    async def close(self):
        await self.model_client.close()
