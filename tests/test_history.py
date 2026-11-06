"""История диалога обрезается последними сообщениями."""

import json

from bot.context import build_context
from bot.storage import UserStorage


async def test_storage_keeps_last_100_messages(storage):
    def add_many(current) -> None:
        dialog_id = current.active_dialog_id
        for index in range(60):
            current.append_exchange(dialog_id, f"u{index}", f"a{index}", 1, 1, 100)

    await storage.update(15, add_many)
    state = await storage.read(15)
    contents = [item.content for item in state.active_dialog.messages]
    assert len(contents) == 100
    assert contents[0] == "u10"
    assert contents[-1] == "a59"


async def test_custom_limit_and_reload_trim(tmp_path):
    storage = UserStorage(tmp_path, max_history_messages=5)
    await storage.read(3)
    path = tmp_path / "3.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["dialogs"][0]["messages"] = [
        {
            "role": "user",
            "content": f"m{index}",
            "timestamp": "2026-01-01T00:00:00+00:00",
        }
        for index in range(10)
    ]
    path.write_text(json.dumps(data), encoding="utf-8")

    state = await storage.read(3)
    assert [item.content for item in state.active_dialog.messages] == [
        "m5",
        "m6",
        "m7",
        "m8",
        "m9",
    ]
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert [item["content"] for item in saved["dialogs"][0]["messages"]] == [
        "m5",
        "m6",
        "m7",
        "m8",
        "m9",
    ]


def test_context_keeps_only_requested_tail():
    history = [{"role": "user", "content": f"m{index}"} for index in range(5)]
    messages = build_context(
        mode_prompt="SYS",
        memories=[],
        history=history,
        user_message="вопрос",
        max_history_messages=2,
        context_window=10_000,
        max_output_tokens=10,
    )
    assert [item["content"] for item in messages] == ["SYS", "m3", "m4", "вопрос"]
