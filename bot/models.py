"""Модель состояния пользователя и операции над диалогами."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
import uuid

from bot.errors import DialogNotFoundError, LastDialogError, ValidationError
from bot.limits import HISTORY_HARD_CAP, MAX_FACT_LENGTH, MAX_FACTS, MAX_TITLE_LENGTH
from bot.modes import DEFAULT_MODE, MODES

SCHEMA_VERSION = 1
_DIALOG_ID = re.compile(r"^dlg_[0-9a-f]{12}$")
_MEMORY_ID = re.compile(r"^mem_[0-9a-f]{12}$")
_ROLES = {"user", "assistant"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _clean_line(value: str, *, empty: str, too_long: str, command: str, limit: int) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValidationError(empty)
    if cleaned.startswith("/"):
        raise ValidationError(command)
    if len(cleaned) > limit:
        raise ValidationError(too_long)
    return cleaned


@dataclass
class ChatMessage:
    role: str
    content: str
    timestamp: str

    def to_dict(self) -> dict[str, str]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
        }


@dataclass
class Dialog:
    id: str
    title: str
    mode: str
    created_at: str
    messages: list[ChatMessage] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "mode": self.mode,
            "created_at": self.created_at,
            "messages": [message.to_dict() for message in self.messages],
        }


@dataclass
class MemoryFact:
    id: str
    text: str
    created_at: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "text": self.text, "created_at": self.created_at}


@dataclass
class TokenStats:
    input_tokens: int = 0
    output_tokens: int = 0
    requests: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "requests": self.requests,
        }


@dataclass
class UserSettings:
    show_token_hints: bool = False

    def to_dict(self) -> dict[str, bool]:
        return {"show_token_hints": self.show_token_hints}


@dataclass
class UserState:
    user_id: int
    active_dialog_id: str
    dialogs: list[Dialog]
    memories: list[MemoryFact]
    stats: TokenStats
    settings: UserSettings
    schema_version: int = SCHEMA_VERSION

    @classmethod
    def create(cls, user_id: int) -> UserState:
        dialog = _make_dialog("Диалог 1")
        return cls(
            user_id=user_id,
            active_dialog_id=dialog.id,
            dialogs=[dialog],
            memories=[],
            stats=TokenStats(),
            settings=UserSettings(),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "user_id": self.user_id,
            "active_dialog_id": self.active_dialog_id,
            "settings": self.settings.to_dict(),
            "stats": self.stats.to_dict(),
            "memories": [fact.to_dict() for fact in self.memories],
            "dialogs": [dialog.to_dict() for dialog in self.dialogs],
        }

    def find_dialog(self, dialog_id: str) -> Dialog | None:
        for dialog in self.dialogs:
            if dialog.id == dialog_id:
                return dialog
        return None

    def require_dialog(self, dialog_id: str) -> Dialog:
        dialog = self.find_dialog(dialog_id)
        if dialog is None:
            raise DialogNotFoundError("Диалог не найден.")
        return dialog

    @property
    def active_dialog(self) -> Dialog:
        found = self.find_dialog(self.active_dialog_id)
        if found is not None:
            return found
        if not self.dialogs:
            dialog = _make_dialog(self._next_title())
            self.dialogs.append(dialog)
            self.active_dialog_id = dialog.id
            return dialog
        self.active_dialog_id = self.dialogs[0].id
        return self.dialogs[0]

    def create_dialog(self) -> Dialog:
        dialog = _make_dialog(self._next_title())
        self.dialogs.append(dialog)
        self.active_dialog_id = dialog.id
        return dialog

    def rename_dialog(self, dialog_id: str, title: str) -> None:
        dialog = self.require_dialog(dialog_id)
        dialog.title = _clean_line(
            title,
            empty="Название не может быть пустым.",
            too_long=f"Название длиннее {MAX_TITLE_LENGTH} символов.",
            command="Название не должно быть командой.",
            limit=MAX_TITLE_LENGTH,
        )

    def delete_dialog(self, dialog_id: str) -> None:
        dialog = self.require_dialog(dialog_id)
        if len(self.dialogs) <= 1:
            raise LastDialogError("Нельзя удалить единственный диалог.")
        self.dialogs = [item for item in self.dialogs if item.id != dialog.id]
        if self.active_dialog_id == dialog.id:
            self.active_dialog_id = self.dialogs[0].id

    def clear_dialog(self, dialog_id: str) -> None:
        self.require_dialog(dialog_id).messages.clear()

    def activate(self, dialog_id: str) -> None:
        self.active_dialog_id = self.require_dialog(dialog_id).id

    def set_mode(self, dialog_id: str, mode_id: str) -> None:
        if mode_id not in MODES:
            raise ValidationError("Неизвестный режим.")
        self.require_dialog(dialog_id).mode = mode_id

    def add_memory(self, text: str) -> MemoryFact:
        if len(self.memories) >= MAX_FACTS:
            raise ValidationError(
                f"Можно сохранить не больше {MAX_FACTS} фактов. Удалите один из них."
            )
        fact = MemoryFact(
            id=new_id("mem"),
            text=_clean_line(
                text,
                empty="Нельзя сохранить пустой факт.",
                too_long=f"Факт длиннее {MAX_FACT_LENGTH} символов.",
                command="Факт не должен начинаться с команды.",
                limit=MAX_FACT_LENGTH,
            ),
            created_at=utc_now(),
        )
        self.memories.append(fact)
        return fact

    def delete_memory(self, memory_id: str) -> None:
        kept = [fact for fact in self.memories if fact.id != memory_id]
        if len(kept) == len(self.memories):
            raise ValidationError("Факт не найден.")
        self.memories = kept

    def append_exchange(
        self,
        dialog_id: str,
        user_text: str,
        assistant_text: str,
        input_tokens: int,
        output_tokens: int,
        history_limit: int,
    ) -> None:
        dialog = self.require_dialog(dialog_id)
        dialog.messages.append(ChatMessage("user", user_text, utc_now()))
        dialog.messages.append(ChatMessage("assistant", assistant_text, utc_now()))
        limit = min(max(int(history_limit), 1), HISTORY_HARD_CAP)
        if len(dialog.messages) > limit:
            dialog.messages = dialog.messages[-limit:]
        self.stats.input_tokens += _non_negative(input_tokens)
        self.stats.output_tokens += _non_negative(output_tokens)
        self.stats.requests += 1

    def _next_title(self) -> str:
        existing = {dialog.title for dialog in self.dialogs}
        number = 1
        while f"Диалог {number}" in existing:
            number += 1
        return f"Диалог {number}"


def _make_dialog(title: str) -> Dialog:
    return Dialog(
        id=new_id("dlg"),
        title=title,
        mode=DEFAULT_MODE,
        created_at=utc_now(),
        messages=[],
    )


def _non_negative(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(0, value)


def parse_user_state(
    data: object,
    expected_user_id: int,
    max_history_messages: int,
) -> tuple[UserState, bool]:
    """Собрать состояние из JSON.

    Возвращает пару из состояния и признака, что файл нужно перезаписать
    из-за починенных полей. При чужом user_id или неизвестной схеме
    выбрасывает ValueError: такой файл нельзя принимать.
    """

    if not isinstance(data, dict):
        raise ValueError("root")
    if data.get("schema_version") not in (None, SCHEMA_VERSION):
        raise ValueError("schema")
    if data.get("user_id") != expected_user_id:
        raise ValueError("user_id")

    repaired = data.get("schema_version") != SCHEMA_VERSION
    limit = min(max(int(max_history_messages), 1), HISTORY_HARD_CAP)
    dialogs, dialogs_repaired = _parse_dialogs(data.get("dialogs"), limit)
    memories, memories_repaired = _parse_memories(data.get("memories"))
    stats, stats_repaired = _parse_stats(data.get("stats"))
    settings, settings_repaired = _parse_settings(data.get("settings"))
    repaired = repaired or dialogs_repaired or memories_repaired or stats_repaired or settings_repaired

    if not dialogs:
        dialogs = [_make_dialog("Диалог 1")]
        repaired = True

    active = data.get("active_dialog_id")
    known = {dialog.id for dialog in dialogs}
    if not isinstance(active, str) or active not in known:
        active = dialogs[0].id
        repaired = True

    state = UserState(
        user_id=expected_user_id,
        active_dialog_id=active,
        dialogs=dialogs,
        memories=memories,
        stats=stats,
        settings=settings,
    )
    return state, repaired


def _parse_dialogs(raw: object, limit: int) -> tuple[list[Dialog], bool]:
    if not isinstance(raw, list):
        return [], True
    dialogs: list[Dialog] = []
    repaired = False
    seen: set[str] = set()
    for item in raw:
        dialog, dialog_repaired = _parse_dialog(item, limit)
        repaired = repaired or dialog_repaired
        if dialog is None:
            repaired = True
            continue
        if dialog.id in seen:
            repaired = True
            continue
        seen.add(dialog.id)
        dialogs.append(dialog)
    return dialogs, repaired


def _parse_dialog(raw: object, limit: int) -> tuple[Dialog | None, bool]:
    if not isinstance(raw, dict):
        return None, True
    dialog_id = raw.get("id")
    title = raw.get("title")
    if not isinstance(dialog_id, str) or _DIALOG_ID.fullmatch(dialog_id) is None:
        return None, True
    if not isinstance(title, str) or not title.strip():
        return None, True
    repaired = False
    mode = raw.get("mode")
    created_at = raw.get("created_at")
    if not isinstance(mode, str) or mode not in MODES:
        mode = DEFAULT_MODE
        repaired = True
    if not isinstance(created_at, str) or not created_at.strip():
        created_at = utc_now()
        repaired = True
    messages, messages_repaired = _parse_messages(raw.get("messages"), limit)
    cleaned_title = " ".join(title.split())[:MAX_TITLE_LENGTH]
    if cleaned_title != title:
        repaired = True
    return Dialog(
        id=dialog_id,
        title=cleaned_title,
        mode=mode,
        created_at=created_at,
        messages=messages,
    ), repaired or messages_repaired


def _parse_messages(raw: object, limit: int) -> tuple[list[ChatMessage], bool]:
    if not isinstance(raw, list):
        return [], True
    messages: list[ChatMessage] = []
    repaired = False
    for item in raw:
        if not isinstance(item, dict):
            repaired = True
            continue
        role = item.get("role")
        content = item.get("content")
        timestamp = item.get("timestamp")
        if role not in _ROLES or not isinstance(content, str) or not content.strip():
            repaired = True
            continue
        if not isinstance(timestamp, str) or not timestamp.strip():
            timestamp = utc_now()
            repaired = True
        messages.append(ChatMessage(role, content, timestamp))
    if len(messages) > limit:
        messages = messages[-limit:]
        repaired = True
    return messages, repaired


def _parse_memories(raw: object) -> tuple[list[MemoryFact], bool]:
    if raw is None:
        return [], True
    if not isinstance(raw, list):
        return [], True
    facts: list[MemoryFact] = []
    repaired = False
    seen: set[str] = set()
    for item in raw:
        if len(facts) >= MAX_FACTS:
            repaired = True
            break
        if not isinstance(item, dict):
            repaired = True
            continue
        text = item.get("text")
        if not isinstance(text, str):
            repaired = True
            continue
        text = " ".join(text.split())
        if not text:
            repaired = True
            continue
        if len(text) > MAX_FACT_LENGTH:
            text = text[:MAX_FACT_LENGTH]
            repaired = True
        memory_id = item.get("id")
        if not isinstance(memory_id, str) or _MEMORY_ID.fullmatch(memory_id) is None or memory_id in seen:
            memory_id = new_id("mem")
            repaired = True
        created_at = item.get("created_at")
        if not isinstance(created_at, str) or not created_at.strip():
            created_at = utc_now()
            repaired = True
        seen.add(memory_id)
        facts.append(MemoryFact(memory_id, text, created_at))
    return facts, repaired


def _parse_stats(raw: object) -> tuple[TokenStats, bool]:
    if not isinstance(raw, dict):
        return TokenStats(), True
    repaired = False
    values: dict[str, int] = {}
    for key in ("input_tokens", "output_tokens", "requests"):
        value = raw.get(key, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            values[key] = 0
            repaired = True
        else:
            values[key] = value
    return TokenStats(**values), repaired


def _parse_settings(raw: object) -> tuple[UserSettings, bool]:
    if not isinstance(raw, dict):
        return UserSettings(), True
    value = raw.get("show_token_hints", False)
    if not isinstance(value, bool):
        return UserSettings(), True
    return UserSettings(show_token_hints=value), False
