"""Ошибка API не меняет историю и не придумывает ответ."""

import asyncio

from bot import texts
from bot.ai_service import humanize_openai_error
from tests.conftest import build_conversation, make_response


class RateLimitError(Exception):
    pass


class AuthenticationError(Exception):
    pass


def test_error_names_become_safe_russian_messages():
    assert humanize_openai_error(RateLimitError("secret prompt")) == texts.RATE_ERROR
    assert humanize_openai_error(AuthenticationError("sk-test")) == texts.AUTH_ERROR
    assert humanize_openai_error(RuntimeError("traceback with user text")) == texts.GENERIC_AI_ERROR
    assert "secret" not in texts.RATE_ERROR
    assert "sk-" not in texts.AUTH_ERROR


async def test_api_error_does_not_change_history_or_tokens(tmp_path):
    storage, conversation, client = build_conversation(tmp_path, RateLimitError("boom"))

    def seed(current) -> None:
        current.append_exchange(current.active_dialog_id, "старый вопрос", "старый ответ", 5, 6, 100)
        current.add_memory("уже сохранённый факт")

    await storage.update(30, seed)
    before = (await storage.read(30)).to_dict()
    result = await conversation.reply(30, "новый вопрос")
    after = (await storage.read(30)).to_dict()
    assert result.ok is False
    assert result.text == texts.RATE_ERROR
    assert after == before
    assert len(client.completions.calls) == 1


async def test_empty_and_too_long_input_do_not_call_model(tmp_path):
    storage, conversation, client = build_conversation(
        tmp_path,
        make_response("не должно вызваться", 1, 1),
        max_input_chars=20,
    )
    empty = await conversation.reply(1, "   \n")
    long = await conversation.reply(1, "я" * 21)
    assert empty.ok is False
    assert long.ok is False
    assert "20" in long.text
    assert client.completions.calls == []
    assert not (tmp_path / "1.json").exists()


async def test_parallel_request_to_same_dialog_is_rejected(tmp_path):
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow(**_kwargs):
        started.set()
        await release.wait()
        return make_response("первый-ответ", 3, 4)

    storage, conversation, client = build_conversation(tmp_path, slow)
    first_task = asyncio.create_task(conversation.reply(1, "первый"))
    await asyncio.wait_for(started.wait(), timeout=2)
    second = await conversation.reply(1, "второй")
    assert second.ok is False
    assert second.text == texts.DIALOG_BUSY
    release.set()
    first = await first_task
    assert first.ok is True
    state = await storage.read(1)
    assert [item.content for item in state.active_dialog.messages] == ["первый", "первый-ответ"]
    assert len(client.completions.calls) == 1
    assert state.stats.requests == 1
