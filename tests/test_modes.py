"""Режимы меняют только активный диалог."""

from bot.modes import MODE_ORDER, MODES


def test_six_distinct_modes():
    assert len(MODES) == 6
    assert len({mode.prompt for mode in MODE_ORDER}) == 6
    titles = [mode.title for mode in MODE_ORDER]
    assert titles == [
        "Обычный помощник",
        "Программист",
        "Преподаватель",
        "Бизнес-консультант",
        "Дружелюбный собеседник",
        "AI-консультант по автоматизации",
    ]
    prompt = MODES["automation"].prompt.casefold()
    assert "бизнес-процесс" in prompt
    assert "повтор" in prompt
    assert "автоматиз" in prompt


async def test_mode_of_another_dialog_stays(storage):
    state = await storage.read(6)
    first = state.active_dialog_id
    await storage.update(6, lambda current: current.create_dialog())
    state = await storage.read(6)
    second = state.active_dialog_id

    def fill_second(current) -> None:
        current.append_exchange(second, "как автоматизировать отчёт", "опишите шаги", 2, 3, 100)
        current.set_mode(second, "programmer")

    await storage.update(6, fill_second)

    def change_first(current) -> None:
        current.activate(first)
        current.set_mode(first, "teacher")

    await storage.update(6, change_first)
    state = await storage.read(6)
    assert state.active_dialog_id == first
    assert state.find_dialog(first).mode == "teacher"
    assert state.find_dialog(first).messages == []
    assert state.find_dialog(second).mode == "programmer"
    assert [item.content for item in state.find_dialog(second).messages] == [
        "как автоматизировать отчёт",
        "опишите шаги",
    ]


async def test_new_dialog_starts_in_assistant_mode(storage):
    await storage.update(6, lambda current: current.set_mode(current.active_dialog_id, "business"))
    await storage.update(6, lambda current: current.create_dialog())
    state = await storage.read(6)
    assert state.dialogs[0].mode == "business"
    assert state.active_dialog.mode == "assistant"
