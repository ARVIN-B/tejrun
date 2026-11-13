import asyncio

from django.core.management.base import BaseCommand

from apps.social_media_chatbot.infrastructure.telegram.manager import (
    TelegramBotManager,
)


class Command(BaseCommand):
    help = "Run and supervise active Telegram bots stored in the database."

    def handle(self, *args, **options):
        self.stdout.write("Starting the social chatbot runtime supervisor.")
        try:
            asyncio.run(TelegramBotManager([]).run())
        except KeyboardInterrupt:
            self.stdout.write("Stopping the social chatbot runtime supervisor.")
