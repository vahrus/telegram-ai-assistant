"""Создание, переключение, переименование, очистка и удаление диалогов."""

import pytest

from bot.errors import DialogNotFoundError, LastDialogError, ValidationError
from tests.conftest import build_conversation, make_response


async def test_create_switch_rename_clear_and_delete(storage):
    state = await storage.read(8)
    original = state.active_dialog_id
    assert len(state.dialogs) == 1
    assert state.active_dialog.title == "Диалог 1"

    await storage.update(8, lambda current: current.create_dialog())
    state = await storage.read(8)
    created = state.active_dialog_id
    assert len(state.dialogs) == 2
    assert created != original
    assert state.active_dialog.title == "Диалог 2"

    await storage.update(8, lambda current: current.rename_dialog(created, "  Заказы\nклиентов  "))
    await storage.update(
        8,
        lambda current: current.append_exchange(created, "вопрос", "ответ", 4, 5, 100),
    )
    state = await storage.read(8)
    assert state.find_dialog(created).title == "Заказы клиентов"
    assert len(state.find_dialog(created).messages) == 2
    assert state.find_dialog(original).messages == []

    await storage.update(8, lambda current: current.clear_dialog(created))
    state = await storage.read(8)
    assert state.find_dialog(created).messages == []
    assert state.find_dialog(created).title == "Заказы клиентов"

    await storage.update(8, lambda current: current.activate(original))
    state = await storage.read(8)
    assert state.active_dialog_id == original

    await storage.update(8, lambda current: current.activate(created))
    await storage.update(8, lambda current: current.delete_dialog(created))
    state = await storage.read(8)
    assert [dialog.id for dialog in state.dialogs] == [original]
    assert state.active_dialog_id == original

    with pytest.raises(LastDialogError):
        await storage.update(8, lambda current: current.delete_dialog(original))
    state = await storage.read(8)
    assert len(state.dialogs) == 1
    assert state.active_dialog_id == original


async def test_rename_rejects_empty_title(storage):
    state = await storage.read(3)
    dialog_id = state.active_dialog_id
    with pytest.raises(ValidationError):
        await storage.update(3, lambda current: current.rename_dialog(dialog_id, "   "))
    assert (await storage.read(3)).active_dialog.title == "Диалог 1"


async def test_cannot_touch_dialog_of_another_user(storage, tmp_path):
    import json

    await storage.read(2)
    data = json.loads((tmp_path / "2.json").read_text(encoding="utf-8"))
    data["dialogs"][0]["id"] = "dlg_abcdefabcdef"
    data["active_dialog_id"] = "dlg_abcdefabcdef"
    (tmp_path / "2.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    before_owner = json.loads((tmp_path / "2.json").read_text(encoding="utf-8"))

    await storage.read(1)
    before_other = (await storage.read(1)).to_dict()
    with pytest.raises(DialogNotFoundError):
        await storage.update(1, lambda current: current.delete_dialog("dlg_abcdefabcdef"))

    assert (await storage.read(1)).to_dict() == before_other
    assert json.loads((tmp_path / "2.json").read_text(encoding="utf-8")) == before_owner


async def test_reply_keeps_other_dialog_untouched(tmp_path):
    storage, conversation, client = build_conversation(
        tmp_path,
        make_response("ответ модели", 8, 3),
    )
    await storage.read(4)

    def prepare(current) -> None:
        current.append_exchange(current.active_dialog_id, "старое", "старый ответ", 1, 1, 100)
        current.create_dialog()

    await storage.update(4, prepare)
    state = await storage.read(4)
    inactive = next(dialog for dialog in state.dialogs if dialog.id != state.active_dialog_id)
    result = await conversation.reply(4, "новый вопрос")
    assert result.ok is True
    updated = await storage.read(4)
    kept = updated.find_dialog(inactive.id)
    assert [item.content for item in kept.messages] == ["старое", "старый ответ"]
    assert [item.content for item in updated.active_dialog.messages] == ["новый вопрос", "ответ модели"]
    assert len(client.completions.calls) == 1
