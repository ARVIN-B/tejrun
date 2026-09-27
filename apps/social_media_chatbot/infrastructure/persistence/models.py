from django.db import models


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
