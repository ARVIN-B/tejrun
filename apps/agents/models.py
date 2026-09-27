from django.db import models


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

    name = models.CharField(max_length=150)

    social_media = models.CharField(
        max_length=20,
        choices=SOCIAL_MEDIA_CHOICES,
    )

    api_key = models.TextField()

    model = models.CharField(
        max_length=150,
    )

    base_url = models.URLField()

    telegram_bot_token = models.TextField()

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
