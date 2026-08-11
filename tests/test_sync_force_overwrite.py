from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.features.syncing.models import ChapterSyncOptions, ChapterSyncResult
from backend.platforms.fanqie.pages.editor import EditorWriteNotReady
from backend.platforms.fanqie.syncing import single
from backend.platforms.fanqie.syncing import applier
from backend.platforms.fanqie.publishing import single as publishing_single
from backend.features.publishing.options import ChapterPublishOptions


def test_local_to_remote_always_overwrites_matching_editor_draft(monkeypatch, tmp_path: Path) -> None:
    local = SimpleNamespace(
        subtitle="相同标题",
        full_title="第1章 相同标题",
        content="相同正文",
        text="第1章 相同标题\n\n相同正文",
    )
    applied: list[dict] = []

    monkeypatch.setattr(single, "open_chapter_editor", lambda *args, **kwargs: None)
    monkeypatch.setattr(single, "save_debug", lambda *args, **kwargs: None)
    monkeypatch.setattr(single, "get_remote_chapter", lambda page: ("相同标题", "相同正文", object(), object()))
    monkeypatch.setattr(single, "get_local_chapter", lambda *args, **kwargs: local)

    def apply_local(*args, **kwargs):
        applied.append(kwargs)
        return ChapterSyncResult(ok=True, changed=True, published=True, message="ok")

    monkeypatch.setattr(single, "apply_local_to_remote", apply_local)

    result = single.run_single_chapter_sync(
        page=object(),
        novel_file=tmp_path / "novel.txt",
        chapter_no=1,
        options=ChapterSyncOptions(
            chapter_manage_url="https://fanqienovel.com/manage",
            verify_after_publish=False,
            git_tracking=False,
        ),
        local_chapter=local,
    )

    assert result.published is True
    assert len(applied) == 1
    assert applied[0]["local"] is local


def test_clear_author_note_runs_before_saving_the_main_draft(monkeypatch) -> None:
    events: list[str] = []
    body = "正文" * 120
    local = SimpleNamespace(content=body)

    monkeypatch.setattr(applier, "fill_locator", lambda *args, **kwargs: None)
    monkeypatch.setattr(applier, "pick_title_and_editor", lambda *args, **kwargs: (object(), object()))
    monkeypatch.setattr(applier, "element_text_or_value", lambda *args, **kwargs: body)
    monkeypatch.setattr(applier, "save_debug", lambda *args, **kwargs: None)
    monkeypatch.setattr(applier, "clear_author_note_and_save", lambda *args, **kwargs: events.append("note"))
    monkeypatch.setattr(applier, "click_save_draft", lambda *args, **kwargs: events.append("draft"))
    monkeypatch.setattr(applier, "submit_after_sync_save", lambda *args, **kwargs: events.append("submit"))

    result = applier.apply_local_to_remote(
        object(),
        chapter_no=1,
        local=local,
        local_title="标题",
        title_loc=object(),
        body_loc=object(),
        options=ChapterSyncOptions(
            chapter_manage_url="https://fanqienovel.com/manage",
            verify_after_publish=False,
            git_tracking=False,
            clear_author_note=True,
        ),
        diff_path=None,
        git_repo=None,
        trace_dir=None,
        log=lambda _message: None,
    )

    assert result.ok is True
    assert events == ["note", "draft", "submit"]


def test_existing_editor_refreshes_body_locator_after_writing_title(monkeypatch) -> None:
    body = "正文" * 120
    local = SimpleNamespace(content=body)
    stale_title = object()
    stale_body = object()
    fresh_title = object()
    fresh_body = object()
    writes: list[tuple[object, str]] = []

    monkeypatch.setattr(applier, "fill_locator", lambda _page, loc, text, **_kwargs: writes.append((loc, text)))
    monkeypatch.setattr(applier, "pick_title_and_editor", lambda _page: (fresh_title, fresh_body))
    monkeypatch.setattr(applier, "element_text_or_value", lambda loc: body if loc is fresh_body else "")
    monkeypatch.setattr(applier, "reported_body_word_count", lambda _page: len(body))
    monkeypatch.setattr(applier, "click_save_draft", lambda *args, **kwargs: None)
    monkeypatch.setattr(applier, "submit_after_sync_save", lambda *args, **kwargs: None)
    monkeypatch.setattr(applier, "save_debug", lambda *args, **kwargs: None)

    result = applier.apply_local_to_remote(
        object(),
        chapter_no=1,
        local=local,
        local_title="标题",
        title_loc=stale_title,
        body_loc=stale_body,
        options=ChapterSyncOptions(
            chapter_manage_url="https://fanqienovel.com/manage",
            verify_after_publish=False,
            git_tracking=False,
        ),
        diff_path=None,
        git_repo=None,
        trace_dir=None,
        log=lambda _message: None,
    )

    assert result.ok is True
    assert writes[:2] == [(stale_title, "标题"), (fresh_body, body)]
    assert all(loc is not stale_body for loc, _text in writes)


def test_same_length_stale_body_never_reaches_save_or_submit(monkeypatch) -> None:
    expected = "甲" * 240
    stale = "乙" * 240
    local = SimpleNamespace(content=expected)
    title_loc = object()
    body_loc = object()
    events: list[str] = []

    monkeypatch.setattr(applier, "fill_locator", lambda *args, **kwargs: None)
    monkeypatch.setattr(applier, "pick_title_and_editor", lambda _page: (title_loc, body_loc))
    monkeypatch.setattr(applier, "get_remote_chapter", lambda _page: ("标题", stale, title_loc, body_loc))
    monkeypatch.setattr(applier, "element_text_or_value", lambda _loc: stale)
    monkeypatch.setattr(applier, "save_failure_debug", lambda *args, **kwargs: None)
    monkeypatch.setattr(applier, "click_save_draft", lambda *args, **kwargs: events.append("save"))
    monkeypatch.setattr(applier, "submit_after_sync_save", lambda *args, **kwargs: events.append("submit"))

    with pytest.raises(EditorWriteNotReady, match="全文回读与本地正文不一致"):
        applier.apply_local_to_remote(
            object(),
            chapter_no=1,
            local=local,
            local_title="标题",
            title_loc=title_loc,
            body_loc=body_loc,
            options=ChapterSyncOptions(
                chapter_manage_url="https://fanqienovel.com/manage",
                verify_after_publish=False,
                git_tracking=False,
            ),
            diff_path=None,
            git_repo=None,
            trace_dir=None,
            log=lambda _message: None,
        )

    assert events == []


def test_publish_clear_author_note_runs_before_saving_draft(monkeypatch) -> None:
    events: list[str] = []
    local = SimpleNamespace(subtitle="标题", content="正文", text="标题\n正文")
    created = SimpleNamespace(
        page=object(),
        chapter_no_loc=object(),
        title_loc=object(),
        body_loc=object(),
    )

    monkeypatch.setattr(publishing_single, "create_remote_chapter_editor", lambda *args, **kwargs: created)
    monkeypatch.setattr(publishing_single, "track_publish_chapter", lambda *args, **kwargs: None)
    monkeypatch.setattr(publishing_single, "fill_locator", lambda *args, **kwargs: None)
    monkeypatch.setattr(publishing_single, "save_debug", lambda *args, **kwargs: None)
    monkeypatch.setattr(publishing_single, "_ensure_body_written", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        publishing_single,
        "clear_author_note_and_save",
        lambda *args, **kwargs: events.append("note"),
    )
    monkeypatch.setattr(
        publishing_single,
        "click_save_draft",
        lambda *args, **kwargs: events.append("draft"),
    )
    monkeypatch.setattr(
        publishing_single,
        "publish_after_save",
        lambda *args, **kwargs: events.append("submit"),
    )

    result = publishing_single.run_single_chapter_publish(
        page=object(),
        chapter_no=1,
        local=local,
        options=ChapterPublishOptions(
            chapter_manage_url="https://fanqienovel.com/manage",
            verify_after_publish=False,
            git_tracking=False,
            clear_author_note=True,
        ),
        log=lambda _message: None,
    )

    assert result.ok is True
    assert events == ["note", "draft", "submit"]
