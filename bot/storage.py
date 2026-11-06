"""JSON-хранилище пользователей: атомарная запись и блокировка."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
import copy
import fcntl
import json
import logging
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone

from bot.limits import HISTORY_HARD_CAP
from bot.models import UserState, parse_user_state

logger = logging.getLogger(__name__)


def resolve_user_path(root: Path, user_id: object) -> Path:
    """Путь только к файлу этого пользователя. Чужие и внешние пути отклоняются."""

    if isinstance(user_id, bool) or not isinstance(user_id, int):
        raise ValueError("Некорректный пользователь.")
    if user_id < 1 or user_id > 10**15:
        raise ValueError("Некорректный пользователь.")
    base = root.resolve()
    path = (base / f"{user_id}.json").resolve()
    if path.parent != base or path.name != f"{user_id}.json":
        raise ValueError("Некорректный путь пользователя.")
    return path


class UserStorage:
    def __init__(self, root: Path, max_history_messages: int = HISTORY_HARD_CAP) -> None:
        if isinstance(max_history_messages, bool) or not isinstance(max_history_messages, int):
            raise ValueError("Некорректный размер истории.")
        if not 1 <= max_history_messages <= HISTORY_HARD_CAP:
            raise ValueError("Размер истории должен быть от 1 до 100.")
        self.root = root
        self.max_history_messages = max_history_messages
        self._locks: dict[int, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def read(self, user_id: int) -> UserState:
        self._checked_id(user_id)
        lock = await self._async_lock(user_id)
        async with lock:
            state = await asyncio.to_thread(self._read_sync, user_id)
        return copy.deepcopy(state)

    async def update(self, user_id: int, mutator: Callable[[UserState], None]) -> UserState:
        self._checked_id(user_id)
        lock = await self._async_lock(user_id)
        async with lock:
            state = await asyncio.to_thread(self._update_sync, user_id, mutator)
        return copy.deepcopy(state)

    def _checked_id(self, user_id: int) -> Path:
        return resolve_user_path(self.root, user_id)

    async def _async_lock(self, user_id: int) -> asyncio.Lock:
        async with self._locks_guard:
            lock = self._locks.get(user_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[user_id] = lock
            return lock

    def _read_sync(self, user_id: int) -> UserState:
        with self._locked(user_id):
            return self._read_unlocked(user_id)

    def _update_sync(self, user_id: int, mutator: Callable[[UserState], None]) -> UserState:
        with self._locked(user_id):
            state = self._read_unlocked(user_id)
            mutator(state)
            self._write_unlocked(state)
            return state

    @contextlib.contextmanager
    def _locked(self, user_id: int):
        path = resolve_user_path(self.root, user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_suffix(".lock")
        handle = open(lock_path, "a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()

    def _read_unlocked(self, user_id: int) -> UserState:
        path = resolve_user_path(self.root, user_id)
        if not path.exists():
            state = UserState.create(user_id)
            self._write_unlocked(state)
            return state
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            state, repaired = parse_user_state(data, user_id, self.max_history_messages)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            self._quarantine(path)
            logger.warning("Повреждённый JSON заменён новым файлом состояния")
            state = UserState.create(user_id)
            self._write_unlocked(state)
            return state
        if repaired:
            self._write_unlocked(state)
        return state

    def _write_unlocked(self, state: UserState) -> None:
        path = resolve_user_path(self.root, state.user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f"tmp-{state.user_id}-",
            suffix=".tmp",
            dir=path.parent,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(state.to_dict(), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        except Exception:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(temporary_name)
            raise

    def _quarantine(self, path: Path) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        target = path.with_name(f"{path.name}.{stamp}.corrupt")
        path.replace(target)
