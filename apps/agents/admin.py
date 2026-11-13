from django.contrib import admin
from django import forms

from .models import Agent, Chatbot


CHATBOT_SECRET_FIELDS = (
    "api_key",
    "telegram_bot_token",
    "platform_api_key",
    "whatsapp_access_token",
    "whatsapp_verify_token",
)


class ChatbotAdminForm(forms.ModelForm):
    SECRET_FIELDS = CHATBOT_SECRET_FIELDS

    class Meta:
        model = Chatbot
        fields = "__all__"
        widgets = {
            name: forms.PasswordInput(attrs={"autocomplete": "new-password"})
            for name in CHATBOT_SECRET_FIELDS
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.SECRET_FIELDS:
            if name in self.fields:
                self.initial[name] = ""

    def _preserve_secret(self, name):
        value = self.cleaned_data.get(name)
        if value:
            return value
        return getattr(self.instance, name, "") or ""

    def clean_api_key(self):
        return self._preserve_secret("api_key")

    def clean_telegram_bot_token(self):
        return self._preserve_secret("telegram_bot_token")

    def clean_platform_api_key(self):
        return self._preserve_secret("platform_api_key")

    def clean_whatsapp_access_token(self):
        return self._preserve_secret("whatsapp_access_token")

    def clean_whatsapp_verify_token(self):
        return self._preserve_secret("whatsapp_verify_token")


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "is_active",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "name",
        "slug",
    )

    prepopulated_fields = {
        "slug": ("name",),
    }


@admin.register(Chatbot)
class ChatbotAdmin(admin.ModelAdmin):
    form = ChatbotAdminForm
    list_display = (
        "name",
        "agent",
        "model",
        "social_media",
        "is_active",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "agent",
        "is_active",
    )

    search_fields = (
        "name",
        "agent__name",
        "model",
    )

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "agent",
                    "name",
                    "is_active",
                )
            },
        ),
        (
            "AI Configuration",
            {
                "fields": (
                    "api_key",
                    "platform_api_key",
                    "model",
                    "base_url",
                    "system_prompt",
                    "brand_name",
                    "website_url",
                    "knowledge_markdown",
                    "whatsapp_access_token",
                    "whatsapp_phone_number_id",
                    "whatsapp_verify_token",
                    "evolution_instance_name",
                    "evolution_webhook_configured",
                )
            },
        ),
        (
            "Telegram",
            {
                "fields": (
                    "telegram_bot_token",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )
