"""Защита от повторных callback и параллельной генерации в одном диалоге."""

from __future__ import annotations

import asyncio
import time

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject


class DialogGuard:
    """Не ставит второй запрос к модели в очередь, а сразу сообщает, что диалог занят."""

    def __init__(self) -> None:
        self._busy: set[tuple[int, str]] = set()
        self._guard = asyncio.Lock()

    async def try_acquire(self, user_id: int, dialog_id: str) -> tuple[int, str] | None:
        key = (user_id, dialog_id)
        async with self._guard:
            if key in self._busy:
                return None
            self._busy.add(key)
            return key

    async def release(self, key: tuple[int, str]) -> None:
        async with self._guard:
            self._busy.discard(key)


class CallbackGuard:
    def __init__(self, ttl: float = 60.0, debounce: float = 0.8) -> None:
        self.ttl = ttl
        self.debounce = debounce
        self._ids: dict[str, float] = {}
        self._keys: dict[tuple[int, str], float] = {}
        self._lock = asyncio.Lock()

    async def allow(self, callback_id: str, user_id: int, data: str) -> bool:
        now = time.monotonic()
        async with self._lock:
            self._expire(now)
            if callback_id in self._ids:
                return False
            fingerprint = (user_id, data)
            previous = self._keys.get(fingerprint)
            if previous is not None and now - previous < self.debounce:
                return False
            self._ids[callback_id] = now
            self._keys[fingerprint] = now
            return True

    def _expire(self, now: float) -> None:
        stale_ids = [key for key, stamp in self._ids.items() if now - stamp > self.ttl]
        for key in stale_ids:
            del self._ids[key]
        stale_keys = [key for key, stamp in self._keys.items() if now - stamp > self.ttl]
        for key in stale_keys:
            del self._keys[key]


class CallbackDedupMiddleware(BaseMiddleware):
    def __init__(self, guard: CallbackGuard) -> None:
        super().__init__()
        self._guard = guard

    async def __call__(
        self,
        handler,
        event: TelegramObject,
        data: dict,
    ):
        if isinstance(event, CallbackQuery) and event.from_user is not None:
            allowed = await self._guard.allow(event.id, event.from_user.id, event.data or "")
            if not allowed:
                await event.answer("Запрос уже обработан")
                return None
        return await handler(event, data)
