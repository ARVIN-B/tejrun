import asyncio

from .bot import (
    TelegramBot,
    TelegramBotConfig,
)


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

        tasks = [
            asyncio.create_task(
                bot.run()
            )
            for bot in self.bots
        ]

        await asyncio.gather(*tasks)

    async def close(self):

        await asyncio.gather(
            *[
                bot.close()
                for bot in self.bots
            ],
            return_exceptions=True,
        )