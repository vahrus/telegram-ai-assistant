"""Команды личного чата."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import Settings
from bot.errors import ValidationError
from bot.handlers.ui import send_view
from bot.keyboards import (
    confirm_clear_keyboard,
    dialogs_keyboard,
    main_menu_keyboard,
    memories_keyboard,
)
from bot.states import MemoryStates
from bot.storage import UserStorage
from bot.texts import HELP_TEXT, START_TEXT, dialogs_text, memories_text, menu_text, stats_text

router = Router(name="commands")
router.message.filter(F.chat.type == ChatType.PRIVATE)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, user_storage: UserStorage) -> None:
    await state.clear()
    user_id = _user_id(message)
    if user_id is None:
        return
    current = await user_storage.read(user_id)
    await send_view(message, START_TEXT + menu_text(current), main_menu_keyboard())


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext, user_storage: UserStorage) -> None:
    await state.clear()
    user_id = _user_id(message)
    if user_id is None:
        return
    current = await user_storage.read(user_id)
    await send_view(message, menu_text(current), main_menu_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext) -> None:
    await state.clear()
    await send_view(message, HELP_TEXT, main_menu_keyboard())


@router.message(Command("dialogs"))
async def cmd_dialogs(message: Message, state: FSMContext, user_storage: UserStorage) -> None:
    await state.clear()
    user_id = _user_id(message)
    if user_id is None:
        return
    current = await user_storage.read(user_id)
    await send_view(message, dialogs_text(current, 0), dialogs_keyboard(current, 0))


@router.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext, user_storage: UserStorage) -> None:
    await state.clear()
    user_id = _user_id(message)
    if user_id is None:
        return
    current = await user_storage.read(user_id)
    dialog = current.active_dialog
    if not dialog.messages:
        await message.answer("История активного диалога уже пуста.")
        return
    await message.answer(
        f"Очистить историю диалога «{dialog.title}»? Сообщений: {len(dialog.messages)}.",
        reply_markup=confirm_clear_keyboard(dialog.id),
    )


@router.message(Command("stats"))
async def cmd_stats(
    message: Message,
    state: FSMContext,
    user_storage: UserStorage,
    app_settings: Settings,
) -> None:
    await state.clear()
    user_id = _user_id(message)
    if user_id is None:
        return
    current = await user_storage.read(user_id)
    await send_view(message, stats_text(current, app_settings.openai_model), main_menu_keyboard())


@router.message(Command("memories"))
async def cmd_memories(message: Message, state: FSMContext, user_storage: UserStorage) -> None:
    await state.clear()
    user_id = _user_id(message)
    if user_id is None:
        return
    current = await user_storage.read(user_id)
    await send_view(message, memories_text(current, 0), memories_keyboard(current, 0))


@router.message(Command("remember"))
async def cmd_remember(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    user_storage: UserStorage,
) -> None:
    await state.clear()
    user_id = _user_id(message)
    if user_id is None:
        return
    payload = (command.args or "").strip()
    if not payload:
        await state.set_state(MemoryStates.waiting_text)
        await message.answer("Напишите факт, который нужно запомнить.\nОтмена: /cancel")
        return
    try:
        updated = await user_storage.update(user_id, lambda current: current.add_memory(payload))
    except ValidationError as exc:
        await message.answer(exc.message)
        return
    await message.answer(
        f"Запомнил. Всего фактов: {len(updated.memories)}.\nОни доступны во всех ваших диалогах.",
        reply_markup=memories_keyboard(updated, 0),
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    await state.clear()
    if current is None:
        await message.answer("Сейчас нечего отменять.")
        return
    await message.answer("Действие отменено.", reply_markup=main_menu_keyboard())


def _user_id(message: Message) -> int | None:
    if message.from_user is None:
        return None
    return message.from_user.id
