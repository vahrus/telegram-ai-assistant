"""Долгосрочные факты сохраняются только по явной команде."""

import pytest

from bot.context import build_context
from bot.errors import ValidationError
from bot.limits import MAX_FACT_LENGTH, MAX_FACTS
from bot.modes import get_mode
from tests.conftest import build_conversation, make_response


async def test_add_list_and_delete_memory(storage):
    await storage.update(1, lambda current: current.add_memory("  Меня зовут Лена  "))
    state = await storage.read(1)
    assert [fact.text for fact in state.memories] == ["Меня зовут Лена"]
    memory_id = state.memories[0].id
    await storage.update(1, lambda current: current.delete_memory(memory_id))
    assert (await storage.read(1)).memories == []


async def test_memory_is_shared_by_dialogs_of_one_user(storage):
    def prepare(current) -> None:
        current.add_memory("Магазин открыт до 19:00")
        current.create_dialog()

    await storage.update(12, prepare)
    state = await storage.read(12)
    assert len(state.dialogs) == 2
    for dialog in state.dialogs:
        messages = build_context(
            mode_prompt=get_mode(dialog.mode).prompt,
            memories=[fact.text for fact in state.memories],
            history=[{"role": item.role, "content": item.content} for item in dialog.messages],
            user_message="Когда вы работаете?",
            max_history_messages=100,
            context_window=10_000,
            max_output_tokens=100,
        )
        assert any("19:00" in item["content"] for item in messages)


async def test_reply_does_not_create_memories(tmp_path):
    storage, conversation, _client = build_conversation(
        tmp_path,
        make_response("Короткий ответ", 10, 4),
    )
    result = await conversation.reply(9, "Запомни, что мой город Казань")
    assert result.ok is True
    state = await storage.read(9)
    assert state.memories == []
    assert [item.content for item in state.active_dialog.messages] == [
        "Запомни, что мой город Казань",
        "Короткий ответ",
    ]


async def test_memory_validation_and_limit(storage):
    with pytest.raises(ValidationError):
        await storage.update(1, lambda current: current.add_memory("   "))
    with pytest.raises(ValidationError):
        await storage.update(1, lambda current: current.add_memory("/remember секрет"))
    with pytest.raises(ValidationError):
        await storage.update(1, lambda current: current.add_memory("а" * (MAX_FACT_LENGTH + 1)))

    def fill(current) -> None:
        for index in range(MAX_FACTS):
            current.add_memory(f"факт {index}")

    await storage.update(1, fill)
    with pytest.raises(ValidationError):
        await storage.update(1, lambda current: current.add_memory("ещё один"))
    assert len((await storage.read(1)).memories) == MAX_FACTS
