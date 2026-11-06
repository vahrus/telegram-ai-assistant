"""Навигация по inline-кнопкам."""

from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.callbacks_data import DialogCB, MemoryCB, MenuCB, ModeCB, SettingsCB
from bot.errors import DialogNotFoundError, LastDialogError
from bot.handlers.ui import show_callback
from bot.keyboards import (
    back_keyboard,
    confirm_clear_keyboard,
    confirm_delete_keyboard,
    confirm_forget_keyboard,
    dialog_keyboard,
    dialogs_keyboard,
    main_menu_keyboard,
    memories_keyboard,
    modes_keyboard,
    settings_keyboard,
)
from bot.states import RenameStates
from bot.storage import UserStorage
from bot.texts import (
    HELP_TEXT,
    confirm_clear_text,
    confirm_delete_text,
    confirm_forget_text,
    dialog_card,
    dialogs_text,
    memories_text,
    menu_text,
    mode_text,
    settings_text,
)

router = Router(name="callbacks")
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)

_DIALOG_ID = re.compile(r"^dlg_[0-9a-f]{12}$")
_MEMORY_ID = re.compile(r"^mem_[0-9a-f]{12}$")


@router.callback_query(MenuCB.filter())
async def on_menu(
    callback: CallbackQuery,
    callback_data: MenuCB,
    state: FSMContext,
    user_storage: UserStorage,
) -> None:
    user_id = _user_id(callback)
    if user_id is None:
        return
    await state.clear()
    action = callback_data.action
    if action == "new":
        updated = await user_storage.update(user_id, lambda current: current.create_dialog())
        created = updated.active_dialog
        text = f"Создан диалог «{created.title}». Он выбран активным.\n\n{menu_text(updated)}"
        await show_callback(callback, text, main_menu_keyboard())
        return
    current = await user_storage.read(user_id)
    if action == "dialogs":
        await show_callback(callback, dialogs_text(current, 0), dialogs_keyboard(current, 0))
        return
    if action == "mode":
        await show_callback(callback, mode_text(current), modes_keyboard(current))
        return
    if action == "settings":
        await show_callback(callback, settings_text(current), settings_keyboard(current))
        return
    if action == "help":
        await show_callback(callback, HELP_TEXT, back_keyboard())
        return
    if action == "back":
        await show_callback(callback, menu_text(current), main_menu_keyboard())
        return
    await callback.answer("Это действие устарело. Откройте /menu", show_alert=True)


@router.callback_query(DialogCB.filter())
async def on_dialog(
    callback: CallbackQuery,
    callback_data: DialogCB,
    state: FSMContext,
    user_storage: UserStorage,
) -> None:
    user_id = _user_id(callback)
    if user_id is None:
        return
    await state.clear()
    action = callback_data.action
    if action == "page":
        current = await user_storage.read(user_id)
        page = _page_number(callback_data.dialog_id)
        await show_callback(callback, dialogs_text(current, page), dialogs_keyboard(current, page))
        return
    if _DIALOG_ID.fullmatch(callback_data.dialog_id) is None:
        await callback.answer("Диалог не найден.", show_alert=True)
        return
    dialog_id = callback_data.dialog_id
    current = await user_storage.read(user_id)
    dialog = current.find_dialog(dialog_id)
    if dialog is None and action != "del_yes":
        await callback.answer("Диалог не найден.", show_alert=True)
        return

    if action == "open" and dialog is not None:
        await show_callback(callback, dialog_card(current, dialog), dialog_keyboard(current, dialog.id))
        return
    if action == "use":
        try:
            updated = await user_storage.update(user_id, lambda item: item.activate(dialog_id))
        except DialogNotFoundError:
            await callback.answer("Диалог не найден.", show_alert=True)
            return
        chosen = updated.require_dialog(dialog_id)
        await show_callback(
            callback,
            f"Активен диалог «{chosen.title}».\n\n{dialog_card(updated, chosen)}",
            dialog_keyboard(updated, chosen.id),
        )
        return
    if action == "rename" and dialog is not None:
        await state.set_state(RenameStates.waiting_title)
        await state.update_data(dialog_id=dialog_id)
        await show_callback(
            callback,
            f"Введите новое название для «{dialog.title}».\nОтмена: /cancel",
            None,
        )
        return
    if action == "clr" and dialog is not None:
        if not dialog.messages:
            await callback.answer("История уже пуста.", show_alert=True)
            return
        await show_callback(callback, confirm_clear_text(dialog), confirm_clear_keyboard(dialog.id))
        return
    if action == "clr_yes":
        try:
            updated = await user_storage.update(user_id, lambda item: item.clear_dialog(dialog_id))
        except DialogNotFoundError:
            await callback.answer("Диалог не найден.", show_alert=True)
            return
        chosen = updated.find_dialog(dialog_id)
        if chosen is None:
            await callback.answer("Диалог не найден.", show_alert=True)
            return
        await show_callback(
            callback,
            f"История диалога «{chosen.title}» очищена.\n\n{dialog_card(updated, chosen)}",
            dialog_keyboard(updated, chosen.id),
        )
        return
    if action == "del" and dialog is not None:
        if len(current.dialogs) <= 1:
            await callback.answer("Нельзя удалить единственный диалог.", show_alert=True)
            return
        await show_callback(callback, confirm_delete_text(dialog), confirm_delete_keyboard(dialog.id))
        return
    if action == "del_yes":
        try:
            updated = await user_storage.update(user_id, lambda item: item.delete_dialog(dialog_id))
        except LastDialogError as exc:
            await callback.answer(exc.message, show_alert=True)
            return
        except DialogNotFoundError:
            await callback.answer("Диалог не найден.", show_alert=True)
            return
        await show_callback(
            callback,
            f"Диалог удалён.\n\n{dialogs_text(updated, 0)}",
            dialogs_keyboard(updated, 0),
        )
        return
    await callback.answer("Это действие устарело. Откройте /menu", show_alert=True)


@router.callback_query(ModeCB.filter())
async def on_mode(
    callback: CallbackQuery,
    callback_data: ModeCB,
    state: FSMContext,
    user_storage: UserStorage,
) -> None:
    user_id = _user_id(callback)
    if user_id is None:
        return
    await state.clear()
    current = await user_storage.read(user_id)
    dialog_id = current.active_dialog.id
    mode_id = callback_data.mode

    def mutate(item) -> None:
        item.set_mode(dialog_id, mode_id)

    try:
        updated = await user_storage.update(user_id, mutate)
    except DialogNotFoundError:
        await callback.answer("Диалог не найден.", show_alert=True)
        return
    except Exception as exc:
        message = getattr(exc, "message", None) or "Не удалось сменить режим."
        await callback.answer(str(message), show_alert=True)
        return
    await show_callback(callback, mode_text(updated), modes_keyboard(updated))


@router.callback_query(SettingsCB.filter())
async def on_settings(
    callback: CallbackQuery,
    callback_data: SettingsCB,
    state: FSMContext,
    user_storage: UserStorage,
) -> None:
    user_id = _user_id(callback)
    if user_id is None:
        return
    await state.clear()
    if callback_data.action == "hints":

        def mutate(item) -> None:
            item.settings.show_token_hints = not item.settings.show_token_hints

        updated = await user_storage.update(user_id, mutate)
        await show_callback(callback, settings_text(updated), settings_keyboard(updated))
        return
    if callback_data.action == "memories":
        current = await user_storage.read(user_id)
        await show_callback(callback, memories_text(current, 0), memories_keyboard(current, 0))
        return
    await callback.answer("Это действие устарело. Откройте /menu", show_alert=True)


@router.callback_query(MemoryCB.filter())
async def on_memory(
    callback: CallbackQuery,
    callback_data: MemoryCB,
    state: FSMContext,
    user_storage: UserStorage,
) -> None:
    user_id = _user_id(callback)
    if user_id is None:
        return
    await state.clear()
    if callback_data.action == "page":
        current = await user_storage.read(user_id)
        page = _page_number(callback_data.memory_id)
        await show_callback(callback, memories_text(current, page), memories_keyboard(current, page))
        return
    if _MEMORY_ID.fullmatch(callback_data.memory_id) is None:
        await callback.answer("Факт не найден.", show_alert=True)
        return
    memory_id = callback_data.memory_id
    current = await user_storage.read(user_id)
    fact = next((item for item in current.memories if item.id == memory_id), None)
    if callback_data.action == "del":
        if fact is None:
            await callback.answer("Факт не найден.", show_alert=True)
            return
        await show_callback(callback, confirm_forget_text(fact.text), confirm_forget_keyboard(fact.id))
        return
    if callback_data.action == "del_yes":
        try:
            updated = await user_storage.update(user_id, lambda item: item.delete_memory(memory_id))
        except Exception as exc:
            message = getattr(exc, "message", None) or "Факт не найден."
            await callback.answer(str(message), show_alert=True)
            return
        await show_callback(callback, f"Факт удалён.\n\n{memories_text(updated, 0)}", memories_keyboard(updated, 0))
        return
    await callback.answer("Это действие устарело. Откройте /menu", show_alert=True)


@router.callback_query()
async def unknown_callback(callback: CallbackQuery) -> None:
    await callback.answer("Кнопка устарела. Откройте /menu", show_alert=True)


def _user_id(callback: CallbackQuery) -> int | None:
    if callback.from_user is None:
        return None
    return callback.from_user.id


def _page_number(value: str) -> int:
    if value.isdigit():
        return int(value)
    return 0
