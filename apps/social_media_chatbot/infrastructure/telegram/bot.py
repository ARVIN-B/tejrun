from dataclasses import dataclass
import logging

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
from apps.agents.models import Chatbot as ChatbotConfig


logger = logging.getLogger(__name__)


@dataclass
class TelegramBotConfig:
    bot_id: str
    token: str
    updated_at: str = ""


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

            telegram_user_id = str(
                message.from_user.id
            )

            chatbot = None
            try:
                bot_config = await self._load_bot_config()
                if bot_config is None:
                    return
                chatbot = AutoGenChatbot(bot_config)
                memory_repository = DjangoChatMemoryRepository()
                use_case = ChatUseCase(
                    chatbot=chatbot,
                    memory_repository=memory_repository,
                )

                response = await use_case.execute(
                    source="telegram",
                    bot_id=self.config.bot_id,
                    external_id=telegram_user_id,
                    message=message.text,
                )

                await message.answer(response)

            except Exception:
                logger.exception("Telegram bot error [%s]", self.config.bot_id)
                await message.answer(
                    "متأسفانه در پردازش پیام مشکلی پیش آمد."
                )
            finally:
                if chatbot is not None:
                    await chatbot.close()

    async def _load_bot_config(self):
        from asgiref.sync import sync_to_async

        @sync_to_async
        def load():
            return ChatbotConfig.objects.filter(
                pk=self.config.bot_id,
                social_media="telegram",
                is_active=True,
            ).first()

        return await load()

    async def run(self):

        logger.info("Starting Telegram bot: %s", self.config.bot_id)

        await self.dp.start_polling(
            self.bot
        )

    async def close(self):

        await self.bot.session.close()
