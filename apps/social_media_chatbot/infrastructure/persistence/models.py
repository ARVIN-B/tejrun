from django.db import models
from django.utils import timezone

from apps.agents.models import Chatbot


class ChatUser(models.Model):
    SOURCE_API = "api"
    SOURCE_TELEGRAM = "telegram"
    SOURCE_WHATSAPP = "whatsapp"

    SOURCE_CHOICES = [
        (SOURCE_API, "API"),
        (SOURCE_TELEGRAM, "Telegram"),
        (SOURCE_WHATSAPP, "WhatsApp"),
    ]

    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
    )

    bot_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    external_id = models.CharField(
        max_length=255,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "source",
                    "bot_id",
                    "external_id",
                ],
                name="unique_chat_user_source_bot_external",
            )
        ]

    def __str__(self):
        return f"{self.source}:{self.bot_id}:{self.external_id}"


class Conversation(models.Model):
    user = models.ForeignKey(
        ChatUser,
        on_delete=models.CASCADE,
        related_name="conversations",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"Conversation #{self.id} - {self.user}"


class Message(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"

    ROLE_CHOICES = [
        (ROLE_USER, "User"),
        (ROLE_ASSISTANT, "Assistant"),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
    )

    content = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["created_at"]

        indexes = [models.Index(fields=["conversation", "created_at"])]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


class InboundMessageEvent(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
    ]

    chatbot = models.ForeignKey(Chatbot, on_delete=models.CASCADE, related_name="inbound_events")
    platform_message_id = models.CharField(max_length=255)
    sender_id = models.CharField(max_length=255)
    message = models.TextField()
    response = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    last_error = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("chatbot", "platform_message_id"),
                name="unique_social_inbound_message",
            )
        ]
        indexes = [
            models.Index(
                fields=("status", "updated_at"),
                name="social_medi_status_25d1ec_idx",
            )
        ]

    def is_stale(self, minutes=5):
        return self.status == self.STATUS_PROCESSING and (
            timezone.now() - self.updated_at
        ).total_seconds() > minutes * 60
