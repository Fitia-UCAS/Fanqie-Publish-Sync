from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from backend.features.syncing.models import ChapterSyncOptions, ChapterSyncResult
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
