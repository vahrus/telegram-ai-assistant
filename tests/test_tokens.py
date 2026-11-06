"""В статистику попадают поля usage, а не длина текста."""

from types import SimpleNamespace

from tests.conftest import build_conversation, make_response


async def test_usage_is_taken_from_api_fields(tmp_path):
    long_text = "а" * 5000
    storage, conversation, _client = build_conversation(
        tmp_path,
        make_response(long_text, prompt_tokens=9, completion_tokens=4),
    )
    result = await conversation.reply(1, "короткий вопрос")
    assert result.ok is True
    assert result.text == long_text
    state = await storage.read(1)
    assert state.stats.input_tokens == 9
    assert state.stats.output_tokens == 4
    assert state.stats.requests == 1
    assert state.stats.input_tokens != len(result.text)
    assert state.stats.output_tokens != len(long_text)

    await conversation.reply(1, "второй")
    state = await storage.read(1)
    assert state.stats.input_tokens == 18
    assert state.stats.output_tokens == 8
    assert state.stats.requests == 2
    assert len(state.active_dialog.messages) == 4


async def test_missing_usage_does_not_invent_tokens(tmp_path):
    storage, conversation, _client = build_conversation(
        tmp_path,
        make_response("ок", usage=None),
    )
    result = await conversation.reply(2, "вопрос")
    assert result.ok is True
    state = await storage.read(2)
    assert state.stats.input_tokens == 0
    assert state.stats.output_tokens == 0
    assert state.stats.requests == 1
    assert [item.content for item in state.active_dialog.messages] == ["вопрос", "ок"]


async def test_input_and_output_token_names_are_preferred(tmp_path):
    usage = SimpleNamespace(
        input_tokens=5,
        output_tokens=6,
        prompt_tokens=100,
        completion_tokens=200,
    )
    storage, conversation, _client = build_conversation(
        tmp_path,
        make_response("ответ", usage=usage),
    )
    await conversation.reply(3, "вопрос")
    state = await storage.read(3)
    assert state.stats.input_tokens == 5
    assert state.stats.output_tokens == 6
