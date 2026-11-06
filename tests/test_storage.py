"""Сохранение JSON, повреждённые файлы и атомарная запись."""

import json

import pytest

from bot import storage as storage_module


async def test_roundtrip_preserves_russian_text_and_stats(storage, tmp_path):
    def fill(current) -> None:
        dialog_id = current.active_dialog_id
        current.rename_dialog(dialog_id, "Косметика")
        current.set_mode(dialog_id, "automation")
        current.add_memory("Доставка по будням")
        current.append_exchange(dialog_id, "вопрос", "ответ", 15, 6, 100)
        current.settings.show_token_hints = True

    await storage.update(1, fill)
    first = (await storage.read(1)).to_dict()
    second = (await storage.read(1)).to_dict()
    assert first == second
    assert first["dialogs"][0]["mode"] == "automation"
    assert first["dialogs"][0]["title"] == "Косметика"
    assert first["memories"][0]["text"] == "Доставка по будням"
    assert first["stats"] == {"input_tokens": 15, "output_tokens": 6, "requests": 1}
    assert first["settings"]["show_token_hints"] is True

    raw = (tmp_path / "1.json").read_text(encoding="utf-8")
    assert "Косметика" in raw
    assert "\\u" not in raw
    assert list(tmp_path.glob("*.tmp")) == []


async def test_corrupt_json_is_replaced_and_backed_up(storage, tmp_path):
    path = tmp_path / "4.json"
    path.write_text("{", encoding="utf-8")
    state = await storage.read(4)
    assert state.user_id == 4
    assert len(state.dialogs) == 1
    backups = list(tmp_path.glob("4.json.*.corrupt"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "{"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["user_id"] == 4
    assert saved["schema_version"] == 1


async def test_failed_replace_keeps_previous_file(storage, tmp_path, monkeypatch):
    await storage.update(1, lambda current: current.add_memory("первый"))

    def fail_replace(*args, **kwargs):
        raise OSError("disk")

    monkeypatch.setattr(storage_module.os, "replace", fail_replace)
    with pytest.raises(OSError):
        await storage.update(1, lambda current: current.add_memory("второй"))

    raw = (tmp_path / "1.json").read_text(encoding="utf-8")
    assert "первый" in raw
    assert "второй" not in raw
    assert list(tmp_path.glob("*.tmp")) == []
    state = await storage.read(1)
    assert [fact.text for fact in state.memories] == ["первый"]


async def test_parallel_updates_do_not_lose_dialogs(storage):
    await storage.read(7)

    async def create(_index: int) -> None:
        await storage.update(7, lambda current: current.create_dialog())

    import asyncio

    await asyncio.gather(*(create(index) for index in range(10)))
    state = await storage.read(7)
    assert len(state.dialogs) == 11
    assert len({dialog.id for dialog in state.dialogs}) == 11
    assert state.active_dialog_id in {dialog.id for dialog in state.dialogs}
