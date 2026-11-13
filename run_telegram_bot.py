import os
import asyncio

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
)

import django

django.setup()

from apps.social_media_chatbot.infrastructure.telegram.manager import (
    TelegramBotManager,
)

if __name__ == "__main__":
    asyncio.run(TelegramBotManager([]).run())
