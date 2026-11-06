"""Состояния пошагового ввода."""

from aiogram.fsm.state import State, StatesGroup


class RenameStates(StatesGroup):
    waiting_title = State()


class MemoryStates(StatesGroup):
    waiting_text = State()
