from __future__ import annotations

from typing import Callable

from backend.platforms.fanqie.syncing.local_source import Chapter
from backend.features.syncing.models import ChapterSyncOptions, ChapterSyncResult
from backend.platforms.fanqie.syncing.submitter import submit_after_sync_save
from backend.platforms.fanqie.syncing.preflight import wait_for_chapter_list_word_counts
from backend.platforms.fanqie.browser.session import save_debug


def verify_single_list_count(
    page,
    *,
    chapter_no: int,
    chapter_manage_url: str,
    local: Chapter,
    log: Callable[[str], None] = print,
) -> None:
    failures = wait_for_chapter_list_word_counts(
        page,
        chapter_manage_url=chapter_manage_url,
        local_chapters={chapter_no: local},
        chapter_numbers=[chapter_no],
        log=log,
    )
    if failures:
        raise RuntimeError(failures[chapter_no])


def confirm_same_content_if_needed(
    page,
    *,
    chapter_no: int,
    options: ChapterSyncOptions,
    local: Chapter,
    log: Callable[[str], None],
) -> ChapterSyncResult | None:
    if not options.is_publish_to_remote:
        return None
    log("编辑页内容已与本地一致，继续执行发布确认。")
    submit_after_sync_save(page, use_ai=options.use_ai, log=log)
    save_debug(page, "after_sync_submit_same_content")
    if options.verify_after_publish:
        verify_single_list_count(
            page,
            chapter_no=chapter_no,
            chapter_manage_url=options.chapter_manage_url,
            local=local,
            log=log,
        )
    msg = "完成：编辑页内容已一致，并已发布确认。"
    log(msg)
    return ChapterSyncResult(ok=True, changed=False, published=True, message=msg)
