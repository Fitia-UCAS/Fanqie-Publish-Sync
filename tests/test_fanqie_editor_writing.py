from __future__ import annotations

import pytest

from backend.platforms.fanqie.pages import editor_fields, editor_writing


class _TextLocator:
    def __init__(self, text: str) -> None:
        self.text = text

    def evaluate(self, script: str, *_args):
        if "tagName" in script:
            return "div"
        return self.text


class _BodyText:
    def __init__(self, text: str) -> None:
        self.text = text

    def inner_text(self, **_kwargs) -> str:
        return self.text


class _CounterPage:
    def __init__(self, count: int) -> None:
        self.count = count

    def locator(self, _selector: str) -> _BodyText:
        return _BodyText(f"正文字数：{self.count}")


def test_body_write_check_rejects_same_prefix_and_suffix_with_different_middle() -> None:
    expected = "开" * 40 + "甲" * 200 + "结" * 40
    stale = "开" * 40 + "乙" * 200 + "结" * 40

    assert editor_writing._text_was_written(_TextLocator(stale), expected) is False


def test_editor_counter_cannot_confirm_a_half_written_body() -> None:
    body = "正文" * 500

    assert editor_fields.editor_body_counter_confirms(_CounterPage(500), body) is False
    assert editor_fields.editor_body_counter_confirms(_CounterPage(950), body) is True


def test_body_write_failure_uses_retryable_editor_exception(monkeypatch) -> None:
    calls = {"paste": 0, "dom": 0, "keyboard": 0}

    class Page:
        def wait_for_timeout(self, _timeout_ms: int) -> None:
            return None

    class Editable:
        def evaluate(self, script: str, *_args):
            if "isContentEditable" in script:
                return True
            if "tagName" in script:
                return "div"
            return None

    monkeypatch.setattr(editor_writing, "save_debug", lambda *args, **kwargs: None)
    monkeypatch.setattr(editor_writing, "_wait_for_editable_ready", lambda *args, **kwargs: True)

    def fail(method: str):
        def run(*args, **kwargs) -> bool:
            calls[method] += 1
            return False

        return run

    monkeypatch.setattr(editor_writing, "_fill_editable_by_paste", fail("paste"))
    monkeypatch.setattr(editor_writing, "_fill_editable_by_dom", fail("dom"))
    monkeypatch.setattr(editor_writing, "_fill_editable_by_keyboard", fail("keyboard"))

    with pytest.raises(editor_fields.EditorWriteNotReady, match="页面未接收到正文内容"):
        editor_writing.fill_locator(Page(), Editable(), "本地正文")

    assert calls == {"paste": 2, "dom": 2, "keyboard": 2}
