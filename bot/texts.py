"""Тексты интерфейса бота."""

from __future__ import annotations

from bot.formatting import page_window
from bot.modes import MODE_ORDER, mode_title
from bot.models import Dialog, UserState

DIALOG_PAGE_SIZE = 6
MEMORY_PAGE_SIZE = 5

EMPTY_INPUT = "Пустое сообщение не отправлено. Напишите вопрос текстом."
DIALOG_BUSY = "Этот диалог ещё отвечает на предыдущее сообщение. Дождитесь завершения."
DIALOG_MISSING = "Активный диалог не найден. Откройте /dialogs и выберите другой."
EMPTY_MODEL = "Модель вернула пустой ответ. История диалога не изменена."
NOT_SAVED = "Ответ показан, но сохранить его в историю не удалось. Повторите запрос позже."
AUTH_ERROR = "Ключ OpenAI отклонён. Проверьте OPENAI_API_KEY в файле .env. История диалога не изменена."
RATE_ERROR = "Сервис ограничил частоту запросов. Подождите немного и повторите. История диалога не изменена."
NETWORK_ERROR = "Не удалось подключиться к OpenAI. Проверьте сеть и повторите. История диалога не изменена."
BAD_REQUEST_ERROR = "Модель не приняла запрос. Сократите сообщение или смените режим. История диалога не изменена."
STATUS_ERROR = "Сервис OpenAI временно недоступен. Повторите позже. История диалога не изменена."
GENERIC_AI_ERROR = "Не получилось получить ответ. История диалога не изменена."

HELP_TEXT = (
    "Справка\n\n"
    "/start — запустить бота и открыть меню\n"
    "/menu — главное меню\n"
    "/help — эта справка\n"
    "/dialogs — список диалогов\n"
    "/reset — очистить историю активного диалога\n"
    "/stats — статистика токенов\n"
    "/remember текст — сохранить факт\n"
    "/memories — показать сохранённые факты\n"
    "/cancel — отменить переименование или ввод факта\n\n"
    "У каждого диалога своя история и свой режим общения. "
    "Смена режима не трогает остальные диалоги.\n\n"
    "Факты из /remember доступны во всех диалогах этого пользователя. "
    "Бот не извлекает и не сохраняет факты сам."
)

START_TEXT = (
    "Я ассистент с отдельными диалогами, режимами общения и долговременными фактами, "
    "которые вы сохраняете сами.\n\n"
)


def too_long(limit: int) -> str:
    return f"Сообщение длиннее {limit} символов. Сократите текст и отправьте снова."


def token_hint(input_tokens: int, output_tokens: int) -> str:
    total = input_tokens + output_tokens
    return f"Использовано токенов: вход {input_tokens}, выход {output_tokens}, всего {total}."


def menu_text(state: UserState) -> str:
    dialog = state.active_dialog
    return (
        "Главное меню\n\n"
        f"Активный диалог: {dialog.title}\n"
        f"Режим: {mode_title(dialog.mode)}\n"
        f"Сообщений: {len(dialog.messages)}\n\n"
        "Выберите действие."
    )


def dialogs_text(state: UserState, page: int) -> str:
    start, end, current, pages = page_window(len(state.dialogs), page, DIALOG_PAGE_SIZE)
    lines = ["Ваши диалоги", ""]
    if not state.dialogs:
        lines.append("Диалогов пока нет.")
    for offset, dialog in enumerate(state.dialogs[start:end], start=start + 1):
        mark = " (активный)" if dialog.id == state.active_dialog_id else ""
        lines.append(
            f"{offset}. {dialog.title}{mark} — {mode_title(dialog.mode)}, "
            f"сообщений: {len(dialog.messages)}"
        )
    if pages > 1:
        lines.extend(["", f"Страница {current + 1} из {pages}"])
    lines.extend(["", "Нажмите на диалог, чтобы открыть его."])
    return "\n".join(lines)


def dialog_card(state: UserState, dialog: Dialog) -> str:
    active = "да" if dialog.id == state.active_dialog_id else "нет"
    created = dialog.created_at.replace("T", " ")
    return (
        f"{dialog.title}\n\n"
        f"Режим: {mode_title(dialog.mode)}\n"
        f"Активный: {active}\n"
        f"Сообщений: {len(dialog.messages)}\n"
        f"Создан: {created}"
    )


def confirm_delete_text(dialog: Dialog) -> str:
    return (
        f"Удалить диалог «{dialog.title}»?\n"
        "История этого диалога исчезнет. Остальные диалоги не изменятся."
    )


def confirm_clear_text(dialog: Dialog) -> str:
    return (
        f"Очистить историю диалога «{dialog.title}»?\n"
        f"Сообщений будет удалено: {len(dialog.messages)}.\n"
        "Сам диалог, его режим и сохранённые факты останутся."
    )


def mode_text(state: UserState) -> str:
    dialog = state.active_dialog
    lines = [
        "Режим активного диалога",
        "",
        f"Диалог: {dialog.title}",
        f"Сейчас: {mode_title(dialog.mode)}",
        "",
        "Новый режим изменит только этот диалог.",
        "",
    ]
    for mode in MODE_ORDER:
        mark = "• " if mode.id == dialog.mode else ""
        lines.append(f"{mark}{mode.title} — {mode.description}")
    return "\n".join(lines)


def settings_text(state: UserState) -> str:
    dialog = state.active_dialog
    hints = "включены" if state.settings.show_token_hints else "выключены"
    return (
        "Настройки\n\n"
        f"Подсказка о токенах после ответа: {hints}\n"
        f"Сохранённых фактов: {len(state.memories)}\n"
        f"История диалога «{dialog.title}»: {len(dialog.messages)} сообщений"
    )


def stats_text(state: UserState, model: str) -> str:
    dialog = state.active_dialog
    total = state.stats.input_tokens + state.stats.output_tokens
    return (
        "Статистика\n\n"
        f"Модель: {model}\n"
        f"Успешных запросов: {state.stats.requests}\n"
        f"Входные токены: {state.stats.input_tokens}\n"
        f"Выходные токены: {state.stats.output_tokens}\n"
        f"Всего токенов: {total}\n\n"
        f"Активный диалог: {dialog.title}\n"
        f"Режим: {mode_title(dialog.mode)}\n"
        f"Сообщений в диалоге: {len(dialog.messages)}\n"
        f"Сохранённых фактов: {len(state.memories)}\n\n"
        "Токены берутся из полей usage ответа API, а не из длины текста."
    )


def memories_text(state: UserState, page: int) -> str:
    if not state.memories:
        return (
            "Сохранённых фактов пока нет.\n\n"
            "Сохранить факт: /remember ваш текст\n"
            "Факты общие для всех диалогов этого пользователя. "
            "Бот не добавляет их автоматически."
        )
    start, end, current, pages = page_window(len(state.memories), page, MEMORY_PAGE_SIZE)
    lines = ["Сохранённые факты", ""]
    for offset, fact in enumerate(state.memories[start:end], start=start + 1):
        lines.append(f"{offset}. {_clip(fact.text, 180)}")
    if pages > 1:
        lines.extend(["", f"Страница {current + 1} из {pages}"])
    lines.extend(["", "Удалить факт можно кнопкой ниже."])
    return "\n".join(lines)


def confirm_forget_text(text: str) -> str:
    return f"Удалить факт?\n\n{_clip(text, 300)}"


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
