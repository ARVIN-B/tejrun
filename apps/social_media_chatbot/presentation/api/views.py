from asgiref.sync import async_to_sync
import json
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.agents.models import Chatbot as ChatbotConfig
from apps.social_media_chatbot.application.use_cases.chat import ChatUseCase
from apps.social_media_chatbot.infrastructure.ai.autogen_chatbot import (
    AutoGenChatbot,
)
from apps.social_media_chatbot.infrastructure.persistence.repositories.django_chat_memory import (
    DjangoChatMemoryRepository,
)
from apps.social_media_chatbot.infrastructure.persistence.models import InboundMessageEvent
from apps.social_media_chatbot.tasks import process_evolution_message

from .serializers import (
    ChatRequestSerializer,
    ChatResponseSerializer,
)


class ChatView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ChatRequestSerializer,
        responses=ChatResponseSerializer,
    )
    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = serializer.validated_data["message"]

        config = ChatbotConfig.objects.filter(
            pk=serializer.validated_data["bot_id"],
            owner=request.user,
            is_active=True,
            social_media__in=("telegram", "whatsapp"),
        ).first()
        if config is None:
            return Response(
                {"detail": "Active chatbot not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        chatbot = AutoGenChatbot(config)
        use_case = ChatUseCase(chatbot, DjangoChatMemoryRepository())
        try:
            response = async_to_sync(use_case.execute)(
                source="api",
                external_id=serializer.validated_data["external_id"],
                message=message,
                bot_id=str(config.pk),
            )
        finally:
            async_to_sync(chatbot.close)()

        return Response(
            {"response": response},
            status=status.HTTP_200_OK,
        )


@csrf_exempt
@require_POST
def evolution_whatsapp_webhook(request, chatbot_id: int, secret: str):
    config = get_object_or_404(
        ChatbotConfig,
        pk=chatbot_id,
        social_media="whatsapp",
        is_active=True,
    )
    if not constant_time_compare(config.social_webhook_secret, secret):
        return HttpResponse(status=404)

    try:
        payload = request.body and json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return HttpResponse(status=400)
    if not isinstance(payload, dict):
        return HttpResponse(status=400)

    event_name = str(payload.get("event", "")).replace(".", "_").upper()
    if event_name not in {"MESSAGES_UPSERT", "CONNECTION_UPDATE"}:
        return HttpResponse(status=200)
    instance = payload.get("instance")
    if instance and instance != config.evolution_instance_name:
        return HttpResponse(status=404)

    data = payload.get("data") or {}
    if event_name == "CONNECTION_UPDATE":
        state_value = data.get("state") or data.get("status")
        if isinstance(state_value, dict):
            state_value = state_value.get("state") or state_value.get("connection")
        if state_value:
            normalized_state = str(state_value).lower()
            if normalized_state in {"open", "connecting", "close"}:
                ChatbotConfig.objects.filter(pk=config.pk).update(
                    whatsapp_connection_state=normalized_state
                )
        return HttpResponse(status=200)

    key = data.get("key") or {}
    if key.get("fromMe"):
        return HttpResponse(status=200)
    sender_id = key.get("remoteJid", "")
    if not sender_id or sender_id.endswith("@g.us") or sender_id.endswith("@broadcast"):
        return HttpResponse(status=200)
    message_data = data.get("message") or {}
    text = message_data.get("conversation") or (
        message_data.get("extendedTextMessage") or {}
    ).get("text")
    platform_message_id = key.get("id")
    if not text or not platform_message_id:
        return HttpResponse(status=200)

    event, created = InboundMessageEvent.objects.get_or_create(
        chatbot=config,
        platform_message_id=str(platform_message_id),
        defaults={
            "sender_id": sender_id,
            "message": text,
        },
    )
    if created or event.status == InboundMessageEvent.STATUS_FAILED or event.is_stale():
        event.status = InboundMessageEvent.STATUS_PENDING
        event.save(update_fields=["status", "updated_at"])
        process_evolution_message.delay(event.pk)
    return HttpResponse(status=200)
