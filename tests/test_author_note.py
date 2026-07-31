from __future__ import annotations

from types import SimpleNamespace

from backend.platforms.fanqie.pages import author_note


def test_clear_author_note_skips_section_that_only_offers_add(monkeypatch) -> None:
    events: list[str] = []

    monkeypatch.setattr(author_note, "_author_note_is_empty", lambda _page: True)
    monkeypatch.setattr(
        author_note,
        "_author_note_editor",
        lambda _page: (_ for _ in ()).throw(AssertionError("不应把正文编辑器识别成作者有话说")),
    )

    page = SimpleNamespace(wait_for_timeout=lambda _timeout: None)
    author_note.clear_author_note_and_save(page, log=events.append)

    assert events == ["“作者有话说”当前为空，无需清理。"]


def test_clear_author_note_skips_open_but_empty_editor(monkeypatch) -> None:
    events: list[str] = []
    editor = object()

    monkeypatch.setattr(author_note, "_author_note_is_empty", lambda _page: False)
    monkeypatch.setattr(author_note, "_author_note_editor", lambda _page: editor)
    monkeypatch.setattr(author_note, "_editor_value", lambda _editor: "")
    monkeypatch.setattr(author_note, "_click_section_action", lambda _editor, action: action == "退出")

    page = SimpleNamespace(wait_for_timeout=lambda _timeout: None)
    author_note.clear_author_note_and_save(page, log=events.append)

    assert events == ["“作者有话说”当前为空，无需清理。"]
