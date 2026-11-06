"""Сборка маршрутов бота."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import ErrorEvent

from bot.handlers.callbacks import router as callbacks_router
from bot.handlers.chat import router as chat_router
from bot.handlers.commands import router as commands_router
from bot.handlers.fsm import router as fsm_router
from bot.handlers.groups import router as groups_router

logger = logging.getLogger(__name__)


def build_router() -> Router:
    root = Router(name="root")
    root.include_router(groups_router)
    root.include_router(commands_router)
    root.include_router(fsm_router)
    root.include_router(callbacks_router)
    root.include_router(chat_router)

    @root.error()
    async def on_error(event: ErrorEvent) -> None:
        # В журнал попадает только тип ошибки, без текста сообщения и секретов.
        logger.error("Необработанная ошибка (%s)", type(event.exception).__name__)

    return root
