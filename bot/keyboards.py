"""Inline-клавиатуры меню, диалогов, режимов и фактов."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.callbacks_data import DialogCB, MemoryCB, MenuCB, ModeCB, SettingsCB
from bot.formatting import page_window
from bot.modes import MODE_ORDER
from bot.models import UserState
from bot.texts import DIALOG_PAGE_SIZE, MEMORY_PAGE_SIZE


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("Новый диалог", MenuCB(action="new").pack())],
            [_button("Список диалогов", MenuCB(action="dialogs").pack())],
            [_button("Сменить режим", MenuCB(action="mode").pack())],
            [_button("Настройки", MenuCB(action="settings").pack())],
            [_button("Помощь", MenuCB(action="help").pack())],
        ]
    )


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_button("Назад", MenuCB(action="back").pack())]]
    )


def dialogs_keyboard(state: UserState, page: int) -> InlineKeyboardMarkup:
    start, end, current, pages = page_window(len(state.dialogs), page, DIALOG_PAGE_SIZE)
    rows: list[list[InlineKeyboardButton]] = []
    for dialog in state.dialogs[start:end]:
        prefix = "• " if dialog.id == state.active_dialog_id else ""
        rows.append(
            [
                _button(
                    _clip(prefix + dialog.title, 40),
                    DialogCB(action="open", dialog_id=dialog.id).pack(),
                )
            ]
        )
    rows.extend(
        _page_nav(current, pages, lambda number: DialogCB(action="page", dialog_id=str(number)).pack())
    )
    rows.append([_button("Новый диалог", MenuCB(action="new").pack())])
    rows.append([_button("Назад", MenuCB(action="back").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dialog_keyboard(state: UserState, dialog_id: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if dialog_id != state.active_dialog_id:
        rows.append(
            [_button("Сделать активным", DialogCB(action="use", dialog_id=dialog_id).pack())]
        )
    rows.append([_button("Переименовать", DialogCB(action="rename", dialog_id=dialog_id).pack())])
    rows.append([_button("Очистить историю", DialogCB(action="clr", dialog_id=dialog_id).pack())])
    if len(state.dialogs) > 1:
        rows.append([_button("Удалить", DialogCB(action="del", dialog_id=dialog_id).pack())])
    rows.append([_button("К списку", MenuCB(action="dialogs").pack())])
    rows.append([_button("В меню", MenuCB(action="back").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_delete_keyboard(dialog_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("Удалить диалог", DialogCB(action="del_yes", dialog_id=dialog_id).pack())],
            [_button("Отмена", DialogCB(action="open", dialog_id=dialog_id).pack())],
        ]
    )


def confirm_clear_keyboard(dialog_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("Да, очистить", DialogCB(action="clr_yes", dialog_id=dialog_id).pack())],
            [_button("Отмена", DialogCB(action="open", dialog_id=dialog_id).pack())],
        ]
    )


def modes_keyboard(state: UserState) -> InlineKeyboardMarkup:
    current = state.active_dialog.mode
    rows = []
    for mode in MODE_ORDER:
        label = f"✓ {mode.title}" if mode.id == current else mode.title
        rows.append([_button(label, ModeCB(mode=mode.id).pack())])
    rows.append([_button("Назад", MenuCB(action="back").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_keyboard(state: UserState) -> InlineKeyboardMarkup:
    hints = "Выключить подсказку о токенах" if state.settings.show_token_hints else "Включить подсказку о токенах"
    dialog_id = state.active_dialog.id
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button(hints, SettingsCB(action="hints").pack())],
            [_button("Сохранённые факты", SettingsCB(action="memories").pack())],
            [_button("Очистить историю диалога", DialogCB(action="clr", dialog_id=dialog_id).pack())],
            [_button("Назад", MenuCB(action="back").pack())],
        ]
    )


def memories_keyboard(state: UserState, page: int) -> InlineKeyboardMarkup:
    start, end, current, pages = page_window(len(state.memories), page, MEMORY_PAGE_SIZE)
    rows: list[list[InlineKeyboardButton]] = []
    for offset, fact in enumerate(state.memories[start:end], start=start + 1):
        rows.append(
            [
                _button(
                    f"Удалить {offset}",
                    MemoryCB(action="del", memory_id=fact.id).pack(),
                )
            ]
        )
    rows.extend(
        _page_nav(current, pages, lambda number: MemoryCB(action="page", memory_id=str(number)).pack())
    )
    rows.append([_button("Назад", MenuCB(action="settings").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_forget_keyboard(memory_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_button("Удалить факт", MemoryCB(action="del_yes", memory_id=memory_id).pack())],
            [_button("Отмена", MemoryCB(action="page", memory_id="0").pack())],
        ]
    )


def _page_nav(current: int, pages: int, pack) -> list[list[InlineKeyboardButton]]:
    if pages <= 1:
        return []
    row: list[InlineKeyboardButton] = []
    if current > 0:
        row.append(_button("←", pack(current - 1)))
    row.append(_button(f"{current + 1}/{pages}", pack(current)))
    if current < pages - 1:
        row.append(_button("→", pack(current + 1)))
    return [row]


def _button(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
