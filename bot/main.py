"""Точка входа: python -m bot.main"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.ai_service import AIService
from bot.bot_commands import BOT_COMMANDS
from bot.config import load_settings
from bot.conversation import ConversationService
from bot.guards import CallbackDedupMiddleware, CallbackGuard
from bot.handlers import build_router
from bot.storage import UserStorage

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    # Журнал aiogram не должен печатать текст апдейтов.
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)

    settings = load_settings()
    user_storage = UserStorage(settings.users_dir, settings.max_history_messages)
    ai_service = AIService(settings)
    conversation = ConversationService(user_storage, ai_service, settings)
    bot = Bot(token=settings.bot_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(build_router())
    dispatcher.callback_query.middleware(CallbackDedupMiddleware(CallbackGuard()))
    dispatcher.workflow_data.update(
        user_storage=user_storage,
        conversation=conversation,
        app_settings=settings,
    )
    logger.info("Бот запущен. Модель: %s", settings.openai_model)
    try:
        await bot.set_my_commands(BOT_COMMANDS)
        await dispatcher.start_polling(bot, drop_pending_updates=True)
    finally:
        await ai_service.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
