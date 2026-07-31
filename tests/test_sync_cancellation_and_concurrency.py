from __future__ import annotations

import pytest

from backend.features.syncing.models import ChapterSyncOptions
from backend.platforms.fanqie.submission import SubmissionFlow, SubmissionMode
from backend.platforms.fanqie.syncing.batch import _split_parallel_chapters
from backend.runtime.errors import TaskCancelled
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
