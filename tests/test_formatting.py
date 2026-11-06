"""Разбиение длинного ответа на сообщения Telegram."""

from bot.formatting import split_message


def test_short_text_stays_one_message():
    assert split_message("Короткий ответ") == ["Короткий ответ"]


def test_long_text_is_split_on_boundaries():
    first = "А" * 50
    second = "Б" * 50
    parts = split_message(f"{first}\n{second}", limit=60)
    assert parts == [first, second]
    assert all(len(part) <= 60 for part in parts)


def test_very_long_line_is_cut_by_limit():
    parts = split_message("я" * 100, limit=40)
    assert "".join(parts) == "я" * 100
    assert all(len(part) <= 40 for part in parts)
    assert len(parts) == 3
