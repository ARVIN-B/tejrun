from dataclasses import dataclass

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from apps.social_media_chatbot.application.use_cases.chat import (
    ChatUseCase,
)
from apps.social_media_chatbot.infrastructure.ai.autogen_chatbot import (
    AutoGenChatbot,
)
from apps.social_media_chatbot.infrastructure.persistence.repositories.django_chat_memory import (
    DjangoChatMemoryRepository,
)


@dataclass
class TelegramBotConfig:
    bot_id: str
    token: str


class TelegramBot:

    def __init__(self, config: TelegramBotConfig):
        self.config = config

        self.bot = Bot(
            token=config.token,
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML,
            ),
        )

        self.dp = Dispatcher()

        self._register_handlers()

    def _register_handlers(self):

        @self.dp.message()
        async def message_handler(message: Message):

            if not message.text:
                return

            if not message.from_user:
                return

            chatbot = AutoGenChatbot()

            memory_repository = (
                DjangoChatMemoryRepository()
            )

            use_case = ChatUseCase(
                chatbot=chatbot,
                memory_repository=memory_repository,
            )

            telegram_user_id = str(
                message.from_user.id
            )

            try:

                response = await use_case.execute(
                    source="telegram",
                    bot_id=self.config.bot_id,
                    external_id=telegram_user_id,
                    message=message.text,
                )

                await message.answer(response)

            except Exception as exc:

                import traceback

                print(
                    f"Telegram bot error "
                    f"[{self.config.bot_id}]: {exc}"
                )

                traceback.print_exc()

                await message.answer(
                    "متأسفانه در پردازش پیام مشکلی پیش آمد."
                )

    async def run(self):

        print(
            f"Starting Telegram bot: "
            f"{self.config.bot_id}"
        )

        await self.dp.start_polling(
            self.bot
        )

    async def close(self):

        await self.bot.session.close()