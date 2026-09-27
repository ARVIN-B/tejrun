import os
import asyncio

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings",
)

import django

django.setup()

from apps.social_media_chatbot.infrastructure.telegram.bot import start_bot

if __name__ == "__main__":
    asyncio.run(start_bot())
