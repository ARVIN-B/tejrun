import asyncio
import logging

from asgiref.sync import sync_to_async
from apps.agents.models import Chatbot

from .bot import (
    TelegramBot,
    TelegramBotConfig,
)

logger = logging.getLogger(__name__)


class TelegramBotManager:

    def __init__(
        self,
        bots: list[TelegramBotConfig],
    ):
        self.bots = [
            TelegramBot(config)
            for config in bots
        ]

    async def run(self):
        running = {}
        try:
            while True:
                configs = await self._active_configs()
                desired = {config.bot_id: config for config in configs}

                for bot_id, (config, bot, task) in list(running.items()):
                    replacement = desired.get(bot_id)
                    if replacement != config or task.done():
                        task.cancel()
                        await asyncio.gather(task, return_exceptions=True)
                        await bot.close()
                        del running[bot_id]

                for bot_id, config in desired.items():
                    if bot_id not in running:
                        bot = TelegramBot(config)
                        task = asyncio.create_task(bot.run(), name=f"telegram-bot-{bot_id}")
                        running[bot_id] = (config, bot, task)

                await asyncio.sleep(10)
        finally:
            for _, bot, task in running.values():
                task.cancel()
                await bot.close()
            await asyncio.gather(
                *(task for _, _, task in running.values()),
                return_exceptions=True,
            )

    @staticmethod
    @sync_to_async
    def _active_configs():
        return [
            TelegramBotConfig(
                bot_id=str(chatbot.pk),
                token=chatbot.platform_api_key or chatbot.telegram_bot_token,
                updated_at=chatbot.updated_at.isoformat(),
            )
            for chatbot in Chatbot.objects.filter(
                social_media="telegram", is_active=True
            ).only("id", "telegram_bot_token", "updated_at")
        ]

    async def close(self):

        await asyncio.gather(
            *[
                bot.close()
                for bot in self.bots
            ],
            return_exceptions=True,
        )
