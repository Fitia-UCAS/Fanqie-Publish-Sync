from __future__ import annotations

from pathlib import Path
from typing import Callable

from backend.features.syncing.models import ChapterSyncResult
from backend.platforms.fanqie.syncing.batch import run_multi_chapter_sync
from backend.features.syncing.options import make_chapter_sync_options
from backend.platforms.fanqie.syncing.remote_catalog import collect_remote_chapter_numbers
from backend.platforms.fanqie.syncing.single import run_single_chapter_sync
from backend.platforms.fanqie.browser.session import BrowserSession
from backend.runtime.defaults import DEFAULT_CHAPTER_MANAGE_URL


def run_chapter_sync(
    novel_file: Path,
    chapter_no: int = 1,
    chapter_manage_url: str = DEFAULT_CHAPTER_MANAGE_URL,
    use_ai: bool = False,
    check_only: bool = False,
    direction: str = "local_to_remote",
    log: Callable[[str], None] = print,
    verify_after_publish: bool = True,
    debug_screenshots: bool = True,
    failure_screenshots: bool = True,
    git_tracking: bool = True,
    auth_state_path: str = "",
    manual_schedule_enabled: bool = False,
    schedule_start_date: str = "",
    schedule_morning_time: str = "10:00",
    schedule_morning_count: int = 1,
    schedule_afternoon_time: str = "18:00",
    schedule_afternoon_count: int = 0,
    stop_requested: Callable[[], bool] | None = None,
) -> ChapterSyncResult:
    options = make_chapter_sync_options(
        chapter_manage_url=chapter_manage_url,
        use_ai=use_ai,
        check_only=check_only,
        direction=direction,
        verify_after_publish=verify_after_publish,
        debug_screenshots=debug_screenshots,
        failure_screenshots=failure_screenshots,
        git_tracking=git_tracking,
        auth_state_path=auth_state_path,
    )
    session = BrowserSession.open(
        debug_category="chapter_sync",
        debug_enabled=debug_screenshots,
        failure_debug_enabled=failure_screenshots,
        auth_state_path=auth_state_path,
    )
    page = session.page
    try:
        return run_single_chapter_sync(page=page, novel_file=novel_file, chapter_no=chapter_no, options=options, log=log)
    finally:
        session.close()


__all__ = [
    "ChapterSyncResult",
    "run_chapter_sync",
    "run_multi_chapter_sync",
    "collect_remote_chapter_numbers",
]
