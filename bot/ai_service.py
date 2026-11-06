"""Клиент OpenAI. Успешный ответ отдаёт текст и фактический usage."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    PermissionDeniedError,
    RateLimitError,
)

from bot.config import Settings
from bot.errors import AIError
from bot import texts

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AIResult:
    text: str
    input_tokens: int
    output_tokens: int


class AIService:
    def __init__(self, settings: Settings, client: object | None = None) -> None:
        self._model = settings.openai_model
        self._max_output_tokens = settings.max_output_tokens
        self._owns_client = client is None
        self._client = client or AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=60.0,
            max_retries=1,
        )

    async def complete(self, messages: list[dict[str, str]]) -> AIResult:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_completion_tokens=self._max_output_tokens,
            )
        except Exception as exc:
            logger.warning("Запрос к модели не выполнен (%s)", type(exc).__name__)
            raise AIError(humanize_openai_error(exc)) from exc

        text = _extract_text(response)
        if not text:
            raise AIError(texts.EMPTY_MODEL)
        incoming, outgoing = _read_usage(getattr(response, "usage", None))
        return AIResult(text=text, input_tokens=incoming, output_tokens=outgoing)

    async def close(self) -> None:
        if not self._owns_client:
            return
        closer = getattr(self._client, "close", None)
        if closer is not None:
            await closer()


def humanize_openai_error(exc: Exception) -> str:
    name = type(exc).__name__
    if isinstance(exc, (AuthenticationError, PermissionDeniedError)) or name in {
        "AuthenticationError",
        "PermissionDeniedError",
    }:
        return texts.AUTH_ERROR
    if isinstance(exc, RateLimitError) or name == "RateLimitError":
        return texts.RATE_ERROR
    if isinstance(exc, (APITimeoutError, APIConnectionError)) or name in {
        "APITimeoutError",
        "APIConnectionError",
    }:
        return texts.NETWORK_ERROR
    if isinstance(exc, BadRequestError) or name == "BadRequestError":
        return texts.BAD_REQUEST_ERROR
    if isinstance(exc, APIStatusError) or name in {"APIStatusError", "InternalServerError"}:
        return texts.STATUS_ERROR
    return texts.GENERIC_AI_ERROR


def _extract_text(response: object) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            text = getattr(item, "text", None)
            if text is None and isinstance(item, dict):
                text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def _read_usage(usage: object | None) -> tuple[int, int]:
    if usage is None:
        return 0, 0
    return (
        _usage_value(usage, "input_tokens", "prompt_tokens"),
        _usage_value(usage, "output_tokens", "completion_tokens"),
    )


def _usage_value(usage: object, *names: str) -> int:
    for name in names:
        if not hasattr(usage, name):
            continue
        value = getattr(usage, name)
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        return max(0, value)
    return 0
