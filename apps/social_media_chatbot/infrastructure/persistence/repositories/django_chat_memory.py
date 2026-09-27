from asgiref.sync import sync_to_async

from apps.social_media_chatbot.domain.repositories.chat_memory import (
    ChatMemoryRepository,
)
from apps.social_media_chatbot.models import (
    ChatUser,
    Conversation,
    Message,
)


class DjangoChatMemoryRepository(ChatMemoryRepository):

    @sync_to_async
    def get_or_create_user(
        self,
        source: str,
        external_id: str,
        bot_id: str | None = None,
    ):
        user, _ = ChatUser.objects.get_or_create(
            source=source,
            bot_id=bot_id,
            external_id=external_id,
        )

        return user

    @sync_to_async
    def get_or_create_conversation(self, user):
        conversation = (
            Conversation.objects.filter(user=user).order_by("-updated_at").first()
        )

        if conversation is None:
            conversation = Conversation.objects.create(
                user=user,
            )

        return conversation

    @sync_to_async
    def get_history(
        self,
        conversation,
        limit: int = 20,
    ):
        messages = list(
            Message.objects.filter(conversation=conversation).order_by("-created_at")[
                :limit
            ]
        )

        messages.reverse()

        return messages

    @sync_to_async
    def save_message(
        self,
        conversation,
        role: str,
        content: str,
    ):
        return Message.objects.create(
            conversation=conversation,
            role=role,
            content=content,
        )
