from __future__ import annotations

from pathlib import Path
from typing import Callable

from backend.platforms.fanqie.publishing.editor import create_remote_chapter_editor
from backend.platforms.fanqie.publishing.submitter import publish_after_save
from backend.platforms.fanqie.publishing.tracker import track_publish_chapter
from backend.platforms.fanqie.publishing.local_source import Chapter, load_local_chapter
from backend.features.publishing.models import ChapterPublishResult
from backend.features.publishing.options import ChapterPublishOptions
from backend.platforms.fanqie.publishing.verifier import verify_single_list_count
from backend.platforms.fanqie.browser.session import save_debug, save_failure_debug
from backend.platforms.fanqie.pages.editor import (
    click_save_draft,
    editor_body_counter_confirms,
    element_text_or_value,
    fill_locator,
    reported_body_word_count,
)
from backend.platforms.fanqie.pages.author_note import clear_author_note_and_save
from backend.features.novel_processing.text_normalizer import normalize_novel_body


def run_single_chapter_publish(
    *,
    page,
    chapter_no: int,
    local: Chapter,
    novel_file: Path | None = None,
    options: ChapterPublishOptions,
    log: Callable[[str], None],
) -> ChapterPublishResult:

    initial_local_title = local.subtitle
    log(f"本地：第 {chapter_no} 章《{initial_local_title}》")

    created = create_remote_chapter_editor(
        page,
        chapter_manage_url=options.chapter_manage_url,
        chapter_no=chapter_no,
        local_title=initial_local_title,
        log=log,
        verify_sequence=False,
    )
    editor_page = created.page

    if novel_file is not None:
        latest_local = load_local_chapter(novel_file, chapter_no)
        if latest_local.text != local.text:
            log(f"检测到第 {chapter_no} 章在任务运行期间发生修改，已重新读取最新正文。")
        local = latest_local
    local_title = local.subtitle
    trace_dir = track_publish_chapter(chapter_no, local, enabled=options.git_tracking, log=log)

    log("正在填写章节序号...")
    save_debug(editor_page, f"chapter_{chapter_no:03d}_before_fill_chapter_no")
    fill_locator(editor_page, created.chapter_no_loc, str(chapter_no))
    save_debug(editor_page, f"chapter_{chapter_no:03d}_after_fill_chapter_no")

    log("正在覆盖标题和完整正文...")
    save_debug(editor_page, f"chapter_{chapter_no:03d}_before_fill_title")
    fill_locator(editor_page, created.title_loc, local_title)
    save_debug(editor_page, f"chapter_{chapter_no:03d}_after_fill_title")

    save_debug(editor_page, f"chapter_{chapter_no:03d}_before_fill_body")
    fill_locator(editor_page, created.body_loc, local.content)
    save_debug(editor_page, f"chapter_{chapter_no:03d}_after_fill_body")
    _ensure_body_written(editor_page, created.body_loc, local, log=log)

    if options.clear_author_note:
        clear_author_note_and_save(editor_page, log=log)

    platform_editor_count = reported_body_word_count(editor_page)
    if platform_editor_count is not None:
        log(f"平台编辑器正文字数：{platform_editor_count}；将用它确认章节列表是否刷新。")

    log("正在保存草稿，等待番茄显示已保存...")
    click_save_draft(editor_page, log=log)
    save_debug(editor_page, f"chapter_{chapter_no:03d}_after_save")

    log("正在进入发布流程：点击右上角“下一步”，并处理错别字/AI 设置/确认发布弹窗...")
    publish_after_save(editor_page, use_ai=options.use_ai, log=log, scheduled_slot=options.schedule_for(chapter_no))
    save_debug(editor_page, f"chapter_{chapter_no:03d}_after_publish")
    if options.verify_after_publish:
        verify_single_list_count(
            editor_page,
            chapter_no=chapter_no,
            chapter_manage_url=options.chapter_manage_url,
            local=local,
            editor_count=platform_editor_count,
            log=log,
        )
        save_debug(editor_page, f"chapter_{chapter_no:03d}_after_list_verify")
    msg = "完成：已自动新建、写入、保存并确认发布。"
    log(msg)
    return ChapterPublishResult(
        ok=True,
        chapter_no=chapter_no,
        published=True,
        message=msg,
        trace_dir=trace_dir,
        platform_editor_count=platform_editor_count,
    )


def _ensure_body_written(page, body_loc, local: Chapter, *, log: Callable[[str], None]) -> None:
    expected_body = normalize_novel_body(local.content)
    written_body = normalize_novel_body(element_text_or_value(body_loc))
    if expected_body and len(written_body) >= max(200, int(len(expected_body) * 0.65)):
        return
    if editor_body_counter_confirms(page, local.content):
        count = reported_body_word_count(page)
        log(f"正文编辑器字数统计已刷新：{count}，继续保存和发布。")
        return

    if expected_body:
        log("正文写入状态读取不稳定，正在重试写入正文...")
        save_debug(page, "body_fill_retry_before")
        fill_locator(page, body_loc, local.content)
        save_debug(page, "body_fill_retry_after")
        written_body = normalize_novel_body(element_text_or_value(body_loc))

    if expected_body and len(written_body) < max(200, int(len(expected_body) * 0.65)):
        if editor_body_counter_confirms(page, local.content):
            count = reported_body_word_count(page)
            log(f"正文编辑器字数统计已刷新：{count}，继续保存和发布。")
            return
        save_failure_debug(page, "body_fill_failed_after_retry")
        raise RuntimeError("正文写入失败：番茄编辑器仍显示正文为空或字数过少。")
