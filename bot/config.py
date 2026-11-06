"""Настройки из окружения. Секреты в код не записываются."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv

from bot.limits import HISTORY_HARD_CAP, MAX_INPUT_CHARS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = "gpt-4.1-mini"

# Опубликованное окно контекста семейства GPT-4.1. Для неизвестной модели
# берётся меньший запас, чтобы запрос не раздувался сверх разумного.
MODEL_CONTEXT_WINDOWS = {
    "gpt-4.1": 1_047_576,
    "gpt-4.1-mini": 1_047_576,
    "gpt-4.1-nano": 1_047_576,
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
}
FALLBACK_CONTEXT_WINDOW = 128_000


@dataclass(frozen=True)
class Settings:
    bot_token: str
    openai_api_key: str
    openai_model: str
    max_history_messages: int
    max_output_tokens: int
    max_input_chars: int
    users_dir: Path
    context_window: int


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    token = os.getenv("BOT_TOKEN", "").strip()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    missing = [
        name
        for name, value in (("BOT_TOKEN", token), ("OPENAI_API_KEY", api_key))
        if not value
    ]
    if missing:
        names = ", ".join(missing)
        raise SystemExit(f"Не заданы переменные окружения: {names}. Заполните файл .env.")

    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    history = _int_env("MAX_HISTORY_MESSAGES", 100, 1, HISTORY_HARD_CAP)
    output_tokens = _int_env("MAX_OUTPUT_TOKENS", 1200, 1, 8192)
    context_window = MODEL_CONTEXT_WINDOWS.get(model, FALLBACK_CONTEXT_WINDOW)
    return Settings(
        bot_token=token,
        openai_api_key=api_key,
        openai_model=model,
        max_history_messages=history,
        max_output_tokens=output_tokens,
        max_input_chars=MAX_INPUT_CHARS,
        users_dir=PROJECT_ROOT / "users",
        context_window=context_window,
    )


def _int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError as exc:
        raise SystemExit(f"{name} должно быть целым числом.") from exc
    if not minimum <= value <= maximum:
        raise SystemExit(f"{name} должно быть в диапазоне {minimum}..{maximum}.")
    return value
