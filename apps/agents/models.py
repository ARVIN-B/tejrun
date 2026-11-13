from django.db import models
from django.conf import settings

from .fields import EncryptedTextField


class Agent(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Chatbot(models.Model):
    SOCIAL_MEDIA_CHOICES = [
        ("telegram", "Telegram"),
        ("whatsapp", "WhatsApp"),
        # ("instagram", "Instagram"),
        # ("facebook", "Facebook"),
        # ("twitter", "Twitter / X"),
        # ("linkedin", "LinkedIn"),
    ]

    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="chatbots",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="social_chatbots",
    )

    name = models.CharField(max_length=150)

    social_media = models.CharField(
        max_length=20,
        choices=SOCIAL_MEDIA_CHOICES,
    )

    # Values are encrypted before persistence. The form/runtime uses the
    # decrypted Python value and never places credentials in templates.
    api_key = EncryptedTextField(blank=True, default="")

    model = models.CharField(max_length=150, blank=True)

    base_url = models.URLField(blank=True)

    telegram_bot_token = EncryptedTextField(blank=True, default="")

    # The credential supplied in the dashboard belongs to the platform
    # (Telegram Bot API or an Evolution API instance), not to the LLM.
    platform_api_key = EncryptedTextField(blank=True, default="")
    evolution_instance_name = models.CharField(max_length=100, blank=True)
    social_webhook_secret = EncryptedTextField(blank=True, default="")
    evolution_webhook_configured = models.BooleanField(default=False)
    whatsapp_connection_state = models.CharField(
        max_length=20,
        default="not_configured",
        choices=(
            ("not_configured", "Not configured"),
            ("creating", "Creating"),
            ("connecting", "Connecting"),
            ("open", "Connected"),
            ("close", "Disconnected"),
            ("error", "Error"),
        ),
    )

    whatsapp_access_token = EncryptedTextField(blank=True, default="")
    whatsapp_phone_number_id = models.CharField(max_length=100, blank=True)
    whatsapp_verify_token = EncryptedTextField(blank=True, default="")

    brand_name = models.CharField(max_length=150, blank=True)
    website_url = models.URLField(blank=True)
    knowledge_markdown = models.TextField(blank=True)

    system_prompt = models.TextField(
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"{self.name} - {self.get_social_media_display()}"
