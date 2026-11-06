"""Сценарий одного ответа: контекст, модель, запись только после успеха."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from bot.ai_service import AIService
from bot.config import Settings
from bot.context import build_context
from bot.errors import AIError, DialogNotFoundError
from bot.guards import DialogGuard
from bot.modes import get_mode
from bot.models import UserState
from bot.storage import UserStorage
from bot import texts

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReplyResult:
    ok: bool
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    show_tokens: bool = False
    saved: bool = True


class ConversationService:
    def __init__(
        self,
        user_storage: UserStorage,
        ai_service: AIService,
        settings: Settings,
        dialog_guard: DialogGuard | None = None,
    ) -> None:
        self._storage = user_storage
        self._ai = ai_service
        self._settings = settings
        self._guard = dialog_guard or DialogGuard()

    async def reply(self, user_id: int, text: str) -> ReplyResult:
        cleaned = text.strip()
        if not cleaned:
            return ReplyResult(ok=False, text=texts.EMPTY_INPUT, saved=False)
        if len(cleaned) > self._settings.max_input_chars:
            return ReplyResult(
                ok=False,
                text=texts.too_long(self._settings.max_input_chars),
                saved=False,
            )

        state = await self._storage.read(user_id)
        dialog_id = state.active_dialog.id
        show_tokens = state.settings.show_token_hints
        key = await self._guard.try_acquire(user_id, dialog_id)
        if key is None:
            return ReplyResult(ok=False, text=texts.DIALOG_BUSY, saved=False)
        try:
            return await self._complete(user_id, dialog_id, cleaned, show_tokens)
        finally:
            await self._guard.release(key)

    async def _complete(
        self,
        user_id: int,
        dialog_id: str,
        cleaned: str,
        show_tokens: bool,
    ) -> ReplyResult:
        state = await self._storage.read(user_id)
        dialog = state.find_dialog(dialog_id)
        if dialog is None:
            return ReplyResult(ok=False, text=texts.DIALOG_MISSING, saved=False)

        try:
            mode = get_mode(dialog.mode)
        except KeyError:
            mode = get_mode("assistant")
        messages = build_context(
            mode_prompt=mode.prompt,
            memories=[fact.text for fact in state.memories],
            history=[
                {"role": item.role, "content": item.content}
                for item in dialog.messages
            ],
            user_message=cleaned,
            max_history_messages=self._settings.max_history_messages,
            context_window=self._settings.context_window,
            max_output_tokens=self._settings.max_output_tokens,
        )
        try:
            result = await self._ai.complete(messages)
        except AIError as exc:
            return ReplyResult(ok=False, text=exc.message, saved=False)

        def mutate(current: UserState) -> None:
            current.append_exchange(
                dialog_id,
                cleaned,
                result.text,
                result.input_tokens,
                result.output_tokens,
                self._settings.max_history_messages,
            )

        try:
            await self._storage.update(user_id, mutate)
        except DialogNotFoundError:
            logger.error("Диалог исчез до сохранения ответа")
            return ReplyResult(
                ok=True,
                text=result.text,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                show_tokens=show_tokens,
                saved=False,
            )
        except Exception as exc:
            logger.error("Не удалось сохранить ответ (%s)", type(exc).__name__)
            return ReplyResult(
                ok=True,
                text=result.text,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                show_tokens=show_tokens,
                saved=False,
            )
        return ReplyResult(
            ok=True,
            text=result.text,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            show_tokens=show_tokens,
            saved=True,
        )
