"""Короткий ответ, если бота позвали не в личном чате."""

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name="groups")
router.message.filter(F.chat.type != ChatType.PRIVATE)


@router.message(CommandStart())
async def group_start(message: Message) -> None:
    await message.answer("Ассистент работает в личном чате. Напишите мне напрямую.")
