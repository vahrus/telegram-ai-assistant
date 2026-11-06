"""Общие фикстуры. OpenAI в тестах не вызывается по сети."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from bot.ai_service import AIService
from bot.config import Settings
from bot.conversation import ConversationService
from bot.storage import UserStorage


def make_response(
    text: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    *,
    usage: object | None = "auto",
):
    if usage == "auto":
        usage = SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    message = SimpleNamespace(content=text, role="assistant")
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice], usage=usage)


class FakeCompletions:
    def __init__(self, responder) -> None:
        self.responder = responder
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        responder = self.responder
        if isinstance(responder, BaseException):
            raise responder
        if callable(responder):
            result = responder(**kwargs)
            if asyncio.iscoroutine(result):
                return await result
            return result
        return responder


class FakeClient:
    def __init__(self, responder) -> None:
        self.completions = FakeCompletions(responder)
        self.chat = SimpleNamespace(completions=self.completions)


def make_settings(tmp_path, **overrides) -> Settings:
    payload = {
        "bot_token": "test-token",
        "openai_api_key": "test-key",
        "openai_model": "gpt-4.1-mini",
        "max_history_messages": 100,
        "max_output_tokens": 256,
        "max_input_chars": 4000,
        "users_dir": tmp_path,
        "context_window": 1_047_576,
    }
    payload.update(overrides)
    return Settings(**payload)


def build_conversation(tmp_path, responder, **setting_overrides):
    settings = make_settings(tmp_path, **setting_overrides)
    storage = UserStorage(tmp_path, settings.max_history_messages)
    client = FakeClient(responder)
    service = AIService(settings, client=client)
    conversation = ConversationService(storage, service, settings)
    return storage, conversation, client


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path)


@pytest.fixture
def storage(tmp_path, settings):
    return UserStorage(tmp_path, settings.max_history_messages)
