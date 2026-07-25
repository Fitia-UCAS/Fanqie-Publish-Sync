from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from backend.features.publishing.models import ChapterPublishResult
from backend.features.publishing.options import make_chapter_publish_options
from backend.features.syncing.models import ChapterSyncResult
from backend.platforms.fanqie.publishing import batch as publish_batch
from backend.platforms.fanqie.syncing import batch as sync_batch


class FakeSession:
    def __init__(self) -> None:
        self.page = object()
        self.context = SimpleNamespace(pages=[self.page])

    def close(self) -> None:
        pass


def _chapter(number: int, content: str) -> Any:
    return SimpleNamespace(number=number, content=content, text=content, subtitle=f"标题{number}")


def test_sync_batch_reloads_chapter_before_each_operation(monkeypatch, tmp_path: Path) -> None:
    novel_file = tmp_path / "novel.txt"
    novel_file.write_text("第1章 标题1\n\n旧正文", encoding="utf-8")
    initial = _chapter(1, "旧正文")
    latest = _chapter(1, "新正文")
    received: list[Any] = []

    monkeypatch.setattr(sync_batch.BrowserSession, "open", lambda **kwargs: FakeSession())
    monkeypatch.setattr(sync_batch, "_local_chapters_by_number", lambda novel_file, chapters: {1: initial})
    monkeypatch.setattr(sync_batch, "_index_editors_if_needed", lambda *args, **kwargs: {})
    monkeypatch.setattr(sync_batch, "get_local_chapter", lambda novel_file, chapter_no: latest)
    monkeypatch.setattr(
        sync_batch,
        "run_single_chapter_sync",
        lambda **kwargs: received.append(kwargs["local_chapter"])
        or ChapterSyncResult(ok=True, changed=False, published=False, message="ok"),
    )

    sync_batch.run_multi_chapter_sync(
        novel_file=novel_file,
        chapters=[1],
        chapter_manage_url="https://fanqienovel.com/manage",
        verify_after_publish=False,
        debug_screenshots=False,
        failure_screenshots=False,
        git_tracking=False,
    )

    assert received == [latest]


def test_publish_batch_reloads_chapter_before_each_operation(monkeypatch, tmp_path: Path) -> None:
    novel_file = tmp_path / "novel.txt"
    novel_file.write_text("第1章 标题1\n\n旧正文", encoding="utf-8")
    initial = _chapter(1, "旧正文")
    latest = _chapter(1, "新正文")
    received: list[Any] = []

    monkeypatch.setattr(publish_batch.BrowserSession, "open", lambda **kwargs: FakeSession())
    monkeypatch.setattr(
        publish_batch,
        "load_local_chapters_by_number",
        lambda novel_file, chapters: {1: initial},
    )
    monkeypatch.setattr(publish_batch, "load_local_chapter", lambda novel_file, chapter_no: latest)
    monkeypatch.setattr(
        publish_batch,
        "run_single_chapter_publish",
        lambda **kwargs: received.append(kwargs["local"])
        or ChapterPublishResult(ok=True, chapter_no=1, published=True, message="ok"),
    )

    publish_batch.run_multi_chapter_publish_with_options(
        novel_file=novel_file,
        chapters=[1],
        options=make_chapter_publish_options(
            chapter_manage_url="https://fanqienovel.com/manage",
            verify_after_publish=False,
            debug_screenshots=False,
            failure_screenshots=False,
            git_tracking=False,
        ),
    )

    assert received == [latest]
