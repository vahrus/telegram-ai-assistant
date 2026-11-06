"""Короткие callback_data в пределах лимита Telegram."""

from aiogram.filters.callback_data import CallbackData


class MenuCB(CallbackData, prefix="menu"):
    action: str


class DialogCB(CallbackData, prefix="dlg"):
    action: str
    dialog_id: str


class ModeCB(CallbackData, prefix="mode"):
    mode: str


class SettingsCB(CallbackData, prefix="set"):
    action: str


class MemoryCB(CallbackData, prefix="mem"):
    action: str
    memory_id: str
