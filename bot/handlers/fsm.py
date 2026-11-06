"""Пошаговое переименование диалога и ввод факта."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.errors import DialogNotFoundError, ValidationError
from bot.keyboards import dialog_keyboard, memories_keyboard
from bot.states import MemoryStates, RenameStates
from bot.storage import UserStorage
from bot.texts import dialog_card

router = Router(name="fsm")
router.message.filter(F.chat.type == ChatType.PRIVATE)


@router.message(RenameStates.waiting_title, F.text)
async def rename_title(message: Message, state: FSMContext, user_storage: UserStorage) -> None:
    user_id = _user_id(message)
    if user_id is None or message.text is None:
        return
    data = await state.get_data()
    dialog_id = data.get("dialog_id")
    if not isinstance(dialog_id, str):
        await state.clear()
        await message.answer("Не удалось понять, какой диалог переименовать. Откройте /dialogs.")
        return
    title = message.text

    def mutate(current) -> None:
        current.rename_dialog(dialog_id, title)

    try:
        updated = await user_storage.update(user_id, mutate)
    except DialogNotFoundError:
        await state.clear()
        await message.answer("Диалог не найден. Откройте /dialogs.")
        return
    except ValidationError as exc:
        await message.answer(f"{exc.message}\nПопробуйте ещё раз или отправьте /cancel.")
        return
    await state.clear()
    dialog = updated.require_dialog(dialog_id)
    await message.answer(
        f"Диалог переименован.\n\n{dialog_card(updated, dialog)}",
        reply_markup=dialog_keyboard(updated, dialog.id),
    )


@router.message(RenameStates.waiting_title)
async def rename_other(message: Message) -> None:
    await message.answer("Нужно отправить текстовое название. Или /cancel для отмены.")


@router.message(MemoryStates.waiting_text, F.text)
async def remember_text(message: Message, state: FSMContext, user_storage: UserStorage) -> None:
    user_id = _user_id(message)
    if user_id is None or message.text is None:
        return
    fact = message.text

    def mutate(current) -> None:
        current.add_memory(fact)

    try:
        updated = await user_storage.update(user_id, mutate)
    except ValidationError as exc:
        await message.answer(f"{exc.message}\nПопробуйте ещё раз или отправьте /cancel.")
        return
    await state.clear()
    await message.answer(
        f"Запомнил. Всего фактов: {len(updated.memories)}.",
        reply_markup=memories_keyboard(updated, 0),
    )


@router.message(MemoryStates.waiting_text)
async def remember_other(message: Message) -> None:
    await message.answer("Нужен текст факта. Или /cancel для отмены.")


def _user_id(message: Message) -> int | None:
    if message.from_user is None:
        return None
    return message.from_user.id
