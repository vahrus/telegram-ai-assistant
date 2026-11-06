"""Порядок контекста: режим, факты, история, новое сообщение."""

from bot.context import build_context
from bot.modes import PROGRAMMER
from tests.conftest import build_conversation, make_response


def test_context_order_with_memories():
    messages = build_context(
        mode_prompt="PROMPT",
        memories=["любит короткий ответ"],
        history=[
            {"role": "user", "content": "старое"},
            {"role": "assistant", "content": "старый ответ"},
            {"role": "system", "content": "это не должно попасть в историю"},
        ],
        user_message="новое",
        max_history_messages=100,
        context_window=10_000,
        max_output_tokens=100,
    )
    assert [item["role"] for item in messages] == [
        "system",
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert messages[0]["content"] == "PROMPT"
    assert "любит короткий ответ" in messages[1]["content"]
    assert messages[2]["content"] == "старое"
    assert messages[3]["content"] == "старый ответ"
    assert messages[-1]["content"] == "новое"
    assert all("не должно попасть" not in item["content"] for item in messages)


def test_token_budget_drops_oldest_history_first():
    from bot.context import estimate_tokens

    history = [
        {"role": "user", "content": "OLDEST " + ("x" * 400)},
        {"role": "assistant", "content": "MIDDLE_MARK"},
        {"role": "user", "content": "NEWEST_MARK"},
    ]
    memory_text = (
        "Долгосрочные факты, которые пользователь явно попросил запомнить. "
        "Используй их, только если они уместны в ответе:\n"
        "- FACT_MARK"
    )
    fixed = estimate_tokens("SYS") + estimate_tokens(memory_text) + estimate_tokens("QUESTION") + 12
    newest = estimate_tokens("NEWEST_MARK") + 4
    budget = fixed + newest
    messages = build_context(
        mode_prompt="SYS",
        memories=["FACT_MARK"],
        history=history,
        user_message="QUESTION",
        max_history_messages=100,
        context_window=budget + 10,
        max_output_tokens=10,
    )
    blob = "\n".join(item["content"] for item in messages)
    assert messages[0]["content"] == "SYS"
    assert "FACT_MARK" in messages[1]["content"]
    assert messages[-1] == {"role": "user", "content": "QUESTION"}
    assert "OLDEST" not in blob
    assert "MIDDLE_MARK" not in blob
    assert "NEWEST_MARK" in blob


async def test_reply_sends_mode_memories_history_and_new_message(tmp_path):
    storage, conversation, client = build_conversation(
        tmp_path,
        make_response("готово", 11, 7),
    )

    def seed(current) -> None:
        dialog_id = current.active_dialog_id
        current.set_mode(dialog_id, "programmer")
        current.add_memory("Пишет на Python")
        current.append_exchange(dialog_id, "ранее", "ответ ранее", 1, 1, 100)

    await storage.update(21, seed)
    result = await conversation.reply(21, "как назвать функцию")
    assert result.ok is True
    sent = client.completions.calls[0]
    assert sent["model"] == "gpt-4.1-mini"
    assert sent["max_completion_tokens"] == 256
    messages = sent["messages"]
    assert messages[0] == {"role": "system", "content": PROGRAMMER.prompt}
    assert "Пишет на Python" in messages[1]["content"]
    assert messages[2]["content"] == "ранее"
    assert messages[3]["content"] == "ответ ранее"
    assert messages[-1] == {"role": "user", "content": "как назвать функцию"}
