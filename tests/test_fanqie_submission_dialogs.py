from __future__ import annotations

import pytest
from playwright.sync_api import Error as PlaywrightError

from backend.platforms.fanqie.dialogs import editing
from backend.platforms.fanqie import submission
from backend.platforms.fanqie.submission import SubmissionFlow, SubmissionMode


class _BodyLocator:
    def __init__(self, page: "_DialogPage") -> None:
        self.page = page

    def inner_text(self, timeout: int = 0) -> str:
        return self.page.body


class _SubmitButton:
    def __init__(self, page: "_DialogPage") -> None:
        self.page = page

    def is_visible(self) -> bool:
        return True

    def is_enabled(self) -> bool:
        return True

    def scroll_into_view_if_needed(self) -> None:
        return None

    def click(self, timeout: int = 0) -> None:
        self.page.clicked += 1


class _ButtonCollection:
    def __init__(self, page: "_DialogPage") -> None:
        self.page = page

    def count(self) -> int:
        return 1

    def nth(self, index: int) -> _SubmitButton:
        return _SubmitButton(self.page)


class _DialogPage:
    def __init__(self, body: str) -> None:
        self.body = body
        self.clicked = 0
        self.waits: list[int] = []

    def locator(self, selector: str) -> _BodyLocator:
        assert selector == "body"
        return _BodyLocator(self)

    def get_by_text(self, text: str, exact: bool = False) -> _ButtonCollection:
        assert text == "提交"
        assert exact is True
        return _ButtonCollection(self)

    def wait_for_timeout(self, timeout: int) -> None:
        self.waits.append(timeout)


def test_non_chapter_prompt_clicks_submit(monkeypatch) -> None:
    page = _DialogPage(
        "提示\n非章节内容请使用“作者有话说”功能，章末附带无关内容可能会影响章节审核结果。"
        "是否确定提交？\n取消\n提交"
    )
    logs: list[str] = []
    monkeypatch.setattr(editing, "save_debug", lambda *args, **kwargs: None)

    handled = editing.click_non_chapter_submit_if_present(page, log=logs.append, timeout_ms=500)

    assert handled is True
    assert page.clicked == 1
    assert logs == ["检测到非章节内容提示，自动点击提交..."]


def test_non_chapter_handler_does_not_click_unrelated_submit(monkeypatch) -> None:
    page = _DialogPage("普通确认\n是否确定提交？\n取消\n提交")
    monkeypatch.setattr(editing, "save_debug", lambda *args, **kwargs: None)

    handled = editing.click_non_chapter_submit_if_present(page, timeout_ms=500)

    assert handled is False
    assert page.clicked == 0


@pytest.mark.parametrize("mode", [SubmissionMode.PUBLISH, SubmissionMode.SYNC])
def test_next_step_handles_typo_then_non_chapter_prompt(monkeypatch, mode) -> None:
    state = {"value": "typo"}
    page = _DialogPage("")

    monkeypatch.setattr(SubmissionFlow, "_click_next_step_once", lambda self: True)
    monkeypatch.setattr(submission, "click_basic_content_check_if_present", lambda *args, **kwargs: False)
    monkeypatch.setattr(submission, "click_continue_edit_if_present", lambda *args, **kwargs: False)
    monkeypatch.setattr(submission, "save_debug", lambda *args, **kwargs: None)
    monkeypatch.setattr(submission, "publish_settings_visible", lambda page: state["value"] == "settings")

    def click_typo(*args, **kwargs) -> bool:
        if state["value"] != "typo":
            return False
        state["value"] = "non_chapter"
        return True

    def click_non_chapter(*args, **kwargs) -> bool:
        if state["value"] != "non_chapter":
            return False
        state["value"] = "settings"
        return True

    monkeypatch.setattr(submission, "click_typo_submit_if_present", click_typo)
    monkeypatch.setattr(submission, "click_non_chapter_submit_if_present", click_non_chapter)

    flow = SubmissionFlow(page=page, mode=mode, log=lambda _message: None)
    flow.enter_settings()

    assert state["value"] == "settings"


def test_blocking_dialog_read_failure_is_diagnostic_and_does_not_report_success(monkeypatch) -> None:
    class BrokenBody:
        def inner_text(self, timeout: int) -> str:
            raise PlaywrightError("body detached")

    class BrokenPage:
        url = "https://fanqienovel.com/publish/123"

        def locator(self, selector: str) -> BrokenBody:
            assert selector == "body"
            return BrokenBody()

    monkeypatch.setattr(submission, "save_failure_debug", lambda *args, **kwargs: None)
    logs: list[str] = []
    flow = SubmissionFlow(BrokenPage(), SubmissionMode.PUBLISH, log=logs.append)

    assert flow._has_blocking_dialog() is True
    assert "阶段=确认提交结果" in logs[0]
    assert "URL=https://fanqienovel.com/publish/123" in logs[0]
    assert "定位器=body" in logs[0]
    assert "body detached" in logs[0]
