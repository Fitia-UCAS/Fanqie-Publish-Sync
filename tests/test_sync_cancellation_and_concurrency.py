from __future__ import annotations

from threading import Event

import pytest

from backend.features.syncing.models import ChapterSyncOptions, ChapterSyncResult
from backend.platforms.fanqie.submission import SubmissionFlow, SubmissionMode
from backend.platforms.fanqie.syncing import batch, single
from backend.platforms.fanqie.syncing.batch import _split_parallel_chapters
from backend.platforms.fanqie.pages.editor import EditorFieldsNotReady, EditorWriteNotReady
from backend.runtime.errors import ErrorStage, TaskCancelled
from backend.runtime.jobs.cancellation import CancellationGuard


def test_cancellation_guard_interrupts_a_segmented_page_wait() -> None:
    state = {"stopped": False}

    class Page:
        def wait_for_timeout(self, timeout_ms: int) -> None:
            state["stopped"] = True

    guard = CancellationGuard(lambda: state["stopped"])

    with pytest.raises(TaskCancelled):
        guard.wait_page(Page(), 1000, slice_ms=100)


def test_submission_checks_cancellation_before_clicking_next_step() -> None:
    flow = SubmissionFlow(
        page=object(),
        mode=SubmissionMode.SYNC,
        cancel=CancellationGuard(lambda: True),
    )

    with pytest.raises(TaskCancelled):
        flow.enter_settings()


def test_parallel_sync_only_uses_existing_editor_links() -> None:
    options = ChapterSyncOptions(
        chapter_manage_url="https://fanqienovel.com/manage",
        concurrency=3,
    )

    parallel, serial = _split_parallel_chapters(
        chapters=[1, 2, 3],
        options=options,
        editor_url_cache={1: "edit-1", 3: "edit-3"},
    )

    assert parallel == [1, 3]
    assert serial == [2]


def test_pull_to_local_remains_serial_to_protect_the_txt() -> None:
    options = ChapterSyncOptions(
        chapter_manage_url="https://fanqienovel.com/manage",
        direction="remote_to_local",
        concurrency=3,
    )

    parallel, serial = _split_parallel_chapters(
        chapters=[1, 2],
        options=options,
        editor_url_cache={1: "edit-1", 2: "edit-2"},
    )

    assert parallel == []
    assert serial == [1, 2]


def test_editor_fields_are_rescanned_until_the_title_mounts(monkeypatch) -> None:
    calls = {"read": 0, "discard": 0}

    class Page:
        def wait_for_timeout(self, _timeout_ms: int) -> None:
            return None

    def read_remote(_page):
        calls["read"] += 1
        if calls["read"] < 3:
            raise EditorFieldsNotReady("找到了正文编辑器，但未能识别标题输入框。")
        return "标题", "正文", object(), object()

    def discard(*args, **kwargs) -> bool:
        calls["discard"] += 1
        return False

    monkeypatch.setattr(single, "get_remote_chapter", read_remote)
    monkeypatch.setattr(single, "click_discard_stale_edit_if_present", discard)

    result = single._read_remote_chapter_with_recovery(
        Page(),
        log=lambda _message: None,
        cancel=CancellationGuard(),
    )

    assert result[:2] == ("标题", "正文")
    assert calls == {"read": 3, "discard": 2}


def test_editor_field_recovery_does_not_reload_an_overloaded_parallel_page(monkeypatch) -> None:
    calls = {"read": 0}

    class Page:
        def wait_for_timeout(self, _timeout_ms: int) -> None:
            return None

    def read_remote(_page):
        calls["read"] += 1
        raise EditorFieldsNotReady("字段未就绪")

    monkeypatch.setattr(single, "get_remote_chapter", read_remote)
    monkeypatch.setattr(single, "click_discard_stale_edit_if_present", lambda *args, **kwargs: False)

    with pytest.raises(EditorFieldsNotReady, match="短暂重试后仍未稳定"):
        single._read_remote_chapter_with_recovery(
            Page(),
            log=lambda _message: None,
            cancel=CancellationGuard(),
            max_attempts=3,
        )

    assert calls == {"read": 3}


def test_parallel_editor_load_failure_is_deferred_to_serial_retry(monkeypatch) -> None:
    def run_worker(*, chapter_no: int, **_kwargs) -> ChapterSyncResult:
        if chapter_no == 2:
            return ChapterSyncResult(
                ok=False,
                changed=False,
                published=False,
                message="字段未就绪",
                error_stage=ErrorStage.EDITOR,
            )
        return ChapterSyncResult(ok=True, changed=True, published=True, message="ok")

    monkeypatch.setattr(batch, "_run_indexed_chapter_worker", run_worker)
    state = batch.MultiChapterSyncState([1, 2], [], [])

    retry_serially = batch._process_indexed_chapters_concurrently(
        novel_file=object(),
        chapters=[1, 2],
        base_options=ChapterSyncOptions(
            chapter_manage_url="https://fanqienovel.com/manage",
            concurrency=2,
            verify_after_publish=False,
        ),
        editor_url_cache={1: "edit-1", 2: "edit-2"},
        state=state,
        log=lambda _message: None,
        cancel=CancellationGuard(),
    )

    assert retry_serially == [2]
    assert state.result_chapter_numbers == [1]
    assert state.results[0].ok is True


def test_parallel_editor_write_failure_is_classified_as_retryable(monkeypatch) -> None:
    closed: list[bool] = []

    class Session:
        page = object()

        def close(self, *, save_state: bool = True) -> None:
            closed.append(save_state)

    monkeypatch.setattr(batch.BrowserSession, "open", lambda **_kwargs: Session())
    monkeypatch.setattr(batch, "get_local_chapter", lambda *args, **kwargs: object())
    monkeypatch.setattr(batch, "save_failure_debug", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        batch,
        "run_single_chapter_sync",
        lambda **_kwargs: (_ for _ in ()).throw(EditorWriteNotReady("正文编辑器写入失败")),
    )

    result = batch._run_indexed_chapter_worker(
        novel_file=object(),
        chapter_no=7,
        options=ChapterSyncOptions(
            chapter_manage_url="https://fanqienovel.com/manage",
            verify_after_publish=False,
        ),
        editor_url="edit-7",
        log=lambda _message: None,
        cancel=CancellationGuard(),
    )

    assert result.ok is False
    assert result.error_stage == ErrorStage.EDITOR
    assert closed == [False]


def test_first_editor_pressure_stops_launching_new_parallel_chapters(monkeypatch) -> None:
    first_failed = Event()
    keep_second_running = Event()
    started: list[int] = []

    def run_worker(*, chapter_no: int, **_kwargs) -> ChapterSyncResult:
        started.append(chapter_no)
        if chapter_no == 1:
            first_failed.set()
            return ChapterSyncResult(
                ok=False,
                changed=False,
                published=False,
                message="编辑器未稳定",
                error_stage=ErrorStage.EDITOR,
            )
        first_failed.wait(timeout=1)
        keep_second_running.wait(timeout=0.05)
        return ChapterSyncResult(ok=True, changed=True, published=True, message="ok")

    monkeypatch.setattr(batch, "_run_indexed_chapter_worker", run_worker)
    state = batch.MultiChapterSyncState([1, 2, 3, 4], [], [])

    retry_serially = batch._process_indexed_chapters_concurrently(
        novel_file=object(),
        chapters=[1, 2, 3, 4],
        base_options=ChapterSyncOptions(
            chapter_manage_url="https://fanqienovel.com/manage",
            concurrency=2,
            verify_after_publish=False,
        ),
        editor_url_cache={chapter_no: f"edit-{chapter_no}" for chapter_no in range(1, 5)},
        state=state,
        log=lambda _message: None,
        cancel=CancellationGuard(),
    )

    assert sorted(started) == [1, 2]
    assert retry_serially == [1, 3, 4]
    assert state.result_chapter_numbers == [2]


def test_parallel_worker_cancellation_is_propagated_without_silently_dropping_a_chapter(monkeypatch) -> None:
    started: list[int] = []

    def run_worker(*, chapter_no: int, **_kwargs) -> ChapterSyncResult:
        started.append(chapter_no)
        raise TaskCancelled("用户终止")

    monkeypatch.setattr(batch, "_run_indexed_chapter_worker", run_worker)
    state = batch.MultiChapterSyncState([1, 2], [], [])

    with pytest.raises(TaskCancelled):
        batch._process_indexed_chapters_concurrently(
            novel_file=object(),
            chapters=[1, 2],
            base_options=ChapterSyncOptions(
                chapter_manage_url="https://fanqienovel.com/manage",
                concurrency=1,
                verify_after_publish=False,
            ),
            editor_url_cache={1: "edit-1", 2: "edit-2"},
            state=state,
            log=lambda _message: None,
            cancel=CancellationGuard(),
        )

    assert started == [1]
    assert state.results == []


def test_serial_existing_editor_reopens_once_after_retryable_write_failure(monkeypatch) -> None:
    calls = {"run": 0}
    success = ChapterSyncResult(ok=True, changed=True, published=True, message="ok")

    class Page:
        def wait_for_timeout(self, _timeout_ms: int) -> None:
            return None

    def run_single(**_kwargs) -> ChapterSyncResult:
        calls["run"] += 1
        if calls["run"] == 1:
            raise EditorWriteNotReady("正文输入区重挂载")
        return success

    monkeypatch.setattr(batch, "get_local_chapter", lambda *args, **kwargs: object())
    monkeypatch.setattr(batch, "run_single_chapter_sync", run_single)
    state = batch.MultiChapterSyncState([7], [], [])

    batch._process_chapters(
        page=Page(),
        novel_file=object(),
        chapters=[7],
        local_chapters={},
        base_options=ChapterSyncOptions(
            chapter_manage_url="https://fanqienovel.com/manage",
            verify_after_publish=False,
        ),
        editor_url_cache={7: "edit-7"},
        state=state,
        log=lambda _message: None,
        cancel=CancellationGuard(),
    )

    assert calls == {"run": 2}
    assert state.result_chapter_numbers == [7]
    assert state.results == [success]


def test_serial_submit_failure_is_not_blindly_replayed(monkeypatch) -> None:
    calls = {"run": 0}

    def run_single(**_kwargs) -> ChapterSyncResult:
        calls["run"] += 1
        raise RuntimeError("确认发布结果未知")

    monkeypatch.setattr(batch, "get_local_chapter", lambda *args, **kwargs: object())
    monkeypatch.setattr(batch, "run_single_chapter_sync", run_single)
    monkeypatch.setattr(batch, "save_failure_debug", lambda *args, **kwargs: None)
    monkeypatch.setattr(batch, "goto_chapter_manage", lambda *args, **kwargs: None)
    monkeypatch.setattr(batch, "dismiss_popups", lambda *args, **kwargs: None)
    state = batch.MultiChapterSyncState([7], [], [])

    batch._process_chapters(
        page=object(),
        novel_file=object(),
        chapters=[7],
        local_chapters={},
        base_options=ChapterSyncOptions(
            chapter_manage_url="https://fanqienovel.com/manage",
            verify_after_publish=False,
        ),
        editor_url_cache={7: "edit-7"},
        state=state,
        log=lambda _message: None,
        cancel=CancellationGuard(),
    )

    assert calls == {"run": 1}
    assert len(state.results) == 1
    assert state.results[0].error_stage == ErrorStage.CHAPTER
