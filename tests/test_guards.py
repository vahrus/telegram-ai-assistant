"""Повторные callback и длина callback_data."""

from bot.callbacks_data import DialogCB, MemoryCB, MenuCB
from bot.guards import CallbackGuard
from bot.handlers import build_router


async def test_duplicate_callback_and_debounce():
    guard = CallbackGuard(ttl=60, debounce=10)
    assert await guard.allow("cb-1", 10, "menu:new") is True
    assert await guard.allow("cb-1", 10, "menu:new") is False
    assert await guard.allow("cb-2", 10, "menu:new") is False
    assert await guard.allow("cb-3", 11, "menu:new") is True
    assert await guard.allow("cb-4", 10, "menu:help") is True


def test_callback_data_fits_telegram_limit():
    samples = [
        DialogCB(action="del_yes", dialog_id="dlg_0123456789ab").pack(),
        MemoryCB(action="del_yes", memory_id="mem_0123456789ab").pack(),
        MenuCB(action="dialogs").pack(),
    ]
    for packed in samples:
        assert len(packed.encode("utf-8")) <= 64


def test_router_builds():
    router = build_router()
    assert router.name == "root"
