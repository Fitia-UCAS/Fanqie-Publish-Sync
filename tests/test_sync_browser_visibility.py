from __future__ import annotations

import inspect

from backend.platforms.fanqie.browser.session import BrowserSession
from backend.platforms.fanqie.publishing import batch as publishing_batch
from backend.platforms.fanqie.syncing import batch, remote_catalog, service


def test_browser_session_remains_visible_by_default_for_manual_login() -> None:
    assert inspect.signature(BrowserSession.open).parameters["headless"].default is False


def test_automated_sync_entry_points_use_background_browser() -> None:
    for module in (batch, service, publishing_batch):
        assert "headless=options.browser_headless" in inspect.getsource(module)
    assert "headless=True" in inspect.getsource(remote_catalog)
