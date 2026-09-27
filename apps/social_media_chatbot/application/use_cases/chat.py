from apps.social_media_chatbot.infrastructure.ai.autogen_chatbot import (
    AutoGenChatbot,
)


class ChatUseCase:

    def __init__(
        self,
        chatbot,
        memory_repository,
    ):
        self.chatbot = chatbot
        self.memory_repository = memory_repository

    async def execute(
        self,
        source: str,
        external_id: str,
        message: str,
        bot_id: str | None = None,
    ):
        # 1. Find or create user
        user = await self.memory_repository.get_or_create_user(
            source=source,
            external_id=external_id,
            bot_id=bot_id,
        )

        # 2. Find or create conversation
        conversation = await self.memory_repository.get_or_create_conversation(user)

        # 3. Load previous history
        history = await self.memory_repository.get_history(
            conversation=conversation,
            limit=20,
        )

        # 4. Send history + current message to AI
        response = await self.chatbot.chat(
            message=message,
            history=history,
        )

        # 5. Save user's message
        await self.memory_repository.save_message(
            conversation=conversation,
            role="user",
            content=message,
        )

        # 6. Save AI response
        await self.memory_repository.save_message(
            conversation=conversation,
            role="assistant",
            content=response,
        )

        return response
