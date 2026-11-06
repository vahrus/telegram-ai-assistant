"""Пользователи не видят файлы и факты друг друга."""

import json
from pathlib import Path

import pytest

from bot.context import build_context
from bot.modes import get_mode
from bot.storage import resolve_user_path


def test_user_path_cannot_escape(tmp_path):
    assert resolve_user_path(tmp_path, 42) == tmp_path.resolve() / "42.json"
    with pytest.raises(ValueError):
        resolve_user_path(tmp_path, True)
    with pytest.raises(ValueError):
        resolve_user_path(tmp_path, "1")
    with pytest.raises(ValueError):
        resolve_user_path(tmp_path, 0)
    with pytest.raises(ValueError):
        resolve_user_path(tmp_path, -5)


async def test_memories_and_files_are_isolated(storage, tmp_path):
    await storage.update(1, lambda current: current.add_memory("секрет пользователя 1"))
    await storage.update(2, lambda current: current.add_memory("секрет пользователя 2"))
    first = await storage.read(1)
    second = await storage.read(2)
    assert [fact.text for fact in first.memories] == ["секрет пользователя 1"]
    assert [fact.text for fact in second.memories] == ["секрет пользователя 2"]

    file_one = (tmp_path / "1.json").read_text(encoding="utf-8")
    file_two = (tmp_path / "2.json").read_text(encoding="utf-8")
    assert "секрет пользователя 2" not in file_one
    assert "секрет пользователя 1" not in file_two
    assert json.loads(file_one)["user_id"] == 1
    assert json.loads(file_two)["user_id"] == 2

    for state, own, foreign in (
        (first, "секрет пользователя 1", "секрет пользователя 2"),
        (second, "секрет пользователя 2", "секрет пользователя 1"),
    ):
        dialog = state.active_dialog
        messages = build_context(
            mode_prompt=get_mode(dialog.mode).prompt,
            memories=[fact.text for fact in state.memories],
            history=[],
            user_message="Что ты обо мне знаешь?",
            max_history_messages=100,
            context_window=10_000,
            max_output_tokens=100,
        )
        blob = json.dumps(messages, ensure_ascii=False)
        assert own in blob
        assert foreign not in blob


async def test_file_with_foreign_user_id_is_not_adopted(storage, tmp_path):
    await storage.read(5)
    path = tmp_path / "5.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["user_id"] = 9
    data["memories"] = [
        {
            "id": "mem_0123456789ab",
            "text": "чужой факт",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    ]
    path.write_text(json.dumps(data), encoding="utf-8")

    state = await storage.read(5)
    assert state.user_id == 5
    assert state.memories == []
    backups = list(tmp_path.glob("5.json.*.corrupt"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text(encoding="utf-8"))["user_id"] == 9
    assert "чужой факт" not in path.read_text(encoding="utf-8")


def test_secrets_and_user_json_are_gitignored():
    root = Path(__file__).resolve().parents[1]
    ignore = (root / ".gitignore").read_text(encoding="utf-8")
    example = (root / ".env.example").read_text(encoding="utf-8")
    requirements = (root / "requirements.txt").read_text(encoding="utf-8").lower()
    assert ".env\n" in ignore or ignore.startswith(".env\n") or "\n.env\n" in f"\n{ignore}"
    assert ".venv/" in ignore
    assert "__pycache__/" in ignore
    assert ".pytest_cache/" in ignore
    assert "users/*.json" in ignore
    assert "*.log" in ignore
    assert ".DS_Store" in ignore
    assert "BOT_TOKEN=" in example
    assert "OPENAI_API_KEY=" in example
    assert "sk-" not in example
    assert "aiogram" in requirements
    assert "openai" in requirements
    assert "sqlite" not in requirements
    assert "postgres" not in requirements
