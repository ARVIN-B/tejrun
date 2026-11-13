from asgiref.sync import async_to_sync
from celery import shared_task
from django.db import transaction

from apps.agents.models import Chatbot as ChatbotConfig
from apps.social_media_chatbot.application.use_cases.chat import ChatUseCase
from apps.social_media_chatbot.infrastructure.ai.autogen_chatbot import AutoGenChatbot
from apps.social_media_chatbot.infrastructure.persistence.models import InboundMessageEvent
from apps.social_media_chatbot.infrastructure.persistence.repositories.django_chat_memory import (
    DjangoChatMemoryRepository,
)
from apps.social_media_chatbot.infrastructure.whatsapp.evolution import send_text


@shared_task(
    bind=True,
    name="social_media_chatbot.process_evolution_message",
    max_retries=3,
    default_retry_delay=20,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_evolution_message(self, event_id: int):
    with transaction.atomic():
        event = (
            InboundMessageEvent.objects.select_for_update()
            .select_related("chatbot")
            .get(pk=event_id)
        )
        if event.status == InboundMessageEvent.STATUS_SENT:
            return
        if not event.chatbot.is_active:
            event.status = InboundMessageEvent.STATUS_FAILED
            event.last_error = "chatbot_inactive"
            event.save(update_fields=["status", "last_error", "updated_at"])
            return
        if event.status == InboundMessageEvent.STATUS_PROCESSING and not event.is_stale():
            return
        event.status = InboundMessageEvent.STATUS_PROCESSING
        event.last_error = ""
        event.save(update_fields=["status", "last_error", "updated_at"])

    try:
        if not event.response:
            chatbot = AutoGenChatbot(event.chatbot)
            try:
                use_case = ChatUseCase(chatbot, DjangoChatMemoryRepository())
                event.response = async_to_sync(use_case.execute)(
                    source="whatsapp",
                    bot_id=str(event.chatbot_id),
                    external_id=event.sender_id,
                    message=event.message,
                )
                event.save(update_fields=["response", "updated_at"])
            finally:
                async_to_sync(chatbot.close)()
        if not ChatbotConfig.objects.filter(
            pk=event.chatbot_id,
            is_active=True,
            social_media="whatsapp",
        ).exists():
            InboundMessageEvent.objects.filter(pk=event.pk).update(
                status=InboundMessageEvent.STATUS_FAILED,
                last_error="chatbot_inactive",
            )
            return
        send_text(event.chatbot, event.sender_id, event.response)
        InboundMessageEvent.objects.filter(pk=event.pk).update(
            status=InboundMessageEvent.STATUS_SENT,
            last_error="",
        )
    except Exception as exc:
        InboundMessageEvent.objects.filter(pk=event.pk).update(
            status=InboundMessageEvent.STATUS_FAILED,
            last_error=type(exc).__name__[:255],
        )
        raise self.retry(exc=exc, countdown=self.default_retry_delay)
