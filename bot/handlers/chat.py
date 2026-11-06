"""Текстовые сообщения пользователя уходят в активный диалог."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction, ChatType
from aiogram.types import Message

from bot.conversation import ConversationService
from bot.formatting import split_message
from bot.texts import NOT_SAVED, token_hint

logger = logging.getLogger(__name__)

router = Router(name="chat")
router.message.filter(F.chat.type == ChatType.PRIVATE)


@router.message(F.text.startswith("/"))
async def unknown_command(message: Message) -> None:
    await message.answer("Такой команды нет. Список команд: /help")


@router.message(F.text)
async def on_text(message: Message, conversation: ConversationService, bot: Bot) -> None:
    if message.from_user is None or message.text is None:
        return
    stop = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(bot, message.chat.id, stop))
    await asyncio.sleep(0)
    try:
        try:
            result = await conversation.reply(message.from_user.id, message.text)
        except Exception as exc:
            logger.error("Сбой обработки сообщения (%s)", type(exc).__name__)
            await message.answer(
                "Произошла внутренняя ошибка. Если ответ не сохранён, история не изменилась."
            )
            return
    finally:
        stop.set()
        typing_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await typing_task

    for part in split_message(result.text):
        await message.answer(part)
    if result.ok and result.show_tokens:
        await message.answer(token_hint(result.input_tokens, result.output_tokens))
    if result.ok and not result.saved:
        await message.answer(NOT_SAVED)


@router.message()
async def unsupported(message: Message) -> None:
    await message.answer("Я принимаю текстовые сообщения. Напишите вопрос или откройте /menu.")


async def _keep_typing(bot: Bot, chat_id: int, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await bot.send_chat_action(chat_id, ChatAction.TYPING)
        except Exception:
            logger.warning("Не удалось отправить статус набора")
        try:
            await asyncio.wait_for(stop.wait(), timeout=4)
        except TimeoutError:
            continue
