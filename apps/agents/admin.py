from django.contrib import admin

from .models import Agent, Chatbot


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
    list_display = (
        "name",
        "agent",
        "model",
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
                    "model",
                    "base_url",
                    "system_prompt",
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