from __future__ import annotations

from typing import Callable

from backend.features.novel_processing.text_normalizer import normalize_novel_body, same_text
from backend.platforms.fanqie.browser.session import save_debug, save_failure_debug
from backend.platforms.fanqie.history.diff_report import make_git_diff
from backend.platforms.fanqie.pages.editor import get_remote_chapter, open_chapter_editor
from backend.runtime.jobs.cancellation import CancellationGuard


def verify_remote_content_matches(
    page,
    *,
    chapter_no: int,
    chapter_manage_url: str,
    local,
    log: Callable[[str], None] = print,
    cancel: CancellationGuard | None = None,
) -> str | None:
    cancel = cancel or CancellationGuard()
    cancel.checkpoint()
    log(f"第 {chapter_no} 章列表字数未能闭环，正在重新打开章节并直接复核平台正文...")
    try:
        open_chapter_editor(
            page,
            chapter_manage_url,
            chapter_no,
            local.subtitle,
            log=log,
            cancel=cancel,
        )
        cancel.checkpoint()
        save_debug(page, f"chapter_{chapter_no:03d}_content_verify_opened")
        remote_title, remote_body, _title_loc, _body_loc = get_remote_chapter(page)
    except Exception as exc:
        save_failure_debug(page, f"chapter_{chapter_no:03d}_content_verify_read_failed")
        return f"正文复核失败：第 {chapter_no} 章无法重新读取平台正文｜{exc}"

    title_same = same_text(local.subtitle, remote_title) or same_text(local.full_title, remote_title)
    body_same = same_text(local.content, remote_body)
    if title_same and body_same:
        log(f"正文复核通过：第 {chapter_no} 章平台最新标题和正文与本地完全一致；忽略字数统计差异。")
        save_debug(page, f"chapter_{chapter_no:03d}_content_verify_matched")
        return None

    diff_path = make_git_diff(
        chapter_no=chapter_no,
        local_title=local.subtitle,
        local_body=local.content,
        remote_title=remote_title,
        remote_body=remote_body,
        direction="local_to_remote",
    )
    save_failure_debug(page, f"chapter_{chapter_no:03d}_content_verify_mismatch")
    local_length = len(normalize_novel_body(local.content))
    remote_length = len(normalize_novel_body(remote_body))
    return (
        f"正文复核失败：第 {chapter_no} 章平台最新内容与本地不一致；"
        f"标题一致={title_same}，规范化正文长度 本地={local_length}、平台={remote_length}；"
        f"差异报告：{diff_path}"
    )


__all__ = ["verify_remote_content_matches"]
