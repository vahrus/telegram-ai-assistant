"""Разбиение длинных текстов под лимит Telegram."""

from __future__ import annotations

from bot.limits import TELEGRAM_MESSAGE_LIMIT


def split_message(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return ["Пустой ответ."]
    if limit < 1:
        raise ValueError("Слишком маленький лимит сообщения.")
    parts: list[str] = []
    rest = cleaned
    while rest:
        if len(rest) <= limit:
            parts.append(rest)
            break
        window = rest[:limit]
        cut = window.rfind("\n")
        if cut < limit // 2:
            cut = window.rfind(" ")
        if cut < limit // 2:
            cut = limit
        chunk = rest[:cut].rstrip()
        rest = rest[cut:].lstrip()
        if chunk:
            parts.append(chunk)
    return parts or ["Пустой ответ."]


def page_window(total: int, page: int, page_size: int) -> tuple[int, int, int, int]:
    """Вернуть start, end, текущую страницу и число страниц."""

    if page_size < 1:
        raise ValueError("page_size")
    if total <= 0:
        return 0, 0, 0, 1
    pages = (total + page_size - 1) // page_size
    current = min(max(page, 0), pages - 1)
    start = current * page_size
    end = min(start + page_size, total)
    return start, end, current, pages
