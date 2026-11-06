"""Команды, которые Telegram показывает в меню бота."""

from aiogram.types import BotCommand

BOT_COMMANDS = [
    BotCommand(command="start", description="Запуск и главное меню"),
    BotCommand(command="menu", description="Главное меню"),
    BotCommand(command="help", description="Справка"),
    BotCommand(command="dialogs", description="Список диалогов"),
    BotCommand(command="reset", description="Очистить историю диалога"),
    BotCommand(command="stats", description="Статистика токенов"),
    BotCommand(command="remember", description="Сохранить факт"),
    BotCommand(command="memories", description="Показать сохранённые факты"),
    BotCommand(command="cancel", description="Отменить текущий ввод"),
]
