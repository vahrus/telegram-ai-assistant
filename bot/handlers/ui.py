"""Показ экранов в сообщениях Telegram."""

from __future__ import annotations

import contextlib
import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot.formatting import split_message

logger = logging.getLogger(__name__)


async def send_view(message: Message, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    parts = split_message(text)
    for index, part in enumerate(parts):
        await message.answer(part, reply_markup=markup if index == len(parts) - 1 else None)


async def show_callback(
    callback: CallbackQuery,
    text: str,
    markup: InlineKeyboardMarkup | None,
) -> None:
    message = callback.message
    if message is None:
        await callback.answer("Откройте чат с ботом заново через /start", show_alert=True)
        return
    with contextlib.suppress(TelegramBadRequest):
        await callback.answer()
    try:
        await message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as exc:
        if "not modified" in str(exc).lower():
            return
        logger.warning("Не удалось обновить сообщение (%s)", type(exc).__name__)
        parts = split_message(text)
        for index, part in enumerate(parts):
            await message.answer(part, reply_markup=markup if index == len(parts) - 1 else None)
