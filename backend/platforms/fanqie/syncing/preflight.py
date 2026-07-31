from __future__ import annotations

from typing import Callable
import time

from backend.platforms.fanqie.syncing.local_source import Chapter
from backend.platforms.fanqie.pages.chapter_list import build_chapter_row_index
from backend.platforms.fanqie.actions.interactions import wait_briefly_for_page_ready
from backend.platforms.fanqie.text_utils import (
    chapter_len,
    is_platform_count_compatible,
    word_count_tolerance,
)
from backend.runtime.errors import TaskCancelled
from backend.runtime.jobs.cancellation import CancellationGuard


def verify_chapter_list_word_counts(
    page,
    *,
    chapter_manage_url: str,
    local_chapters: dict[int, Chapter],
    chapter_numbers: list[int],
    expected_counts: dict[int, int] | None = None,
    log: Callable[[str], None] = print,
) -> dict[int, str]:
    rows = build_chapter_row_index(page, chapter_manage_url, chapter_numbers, log=log)
    failures: dict[int, str] = {}
    for no in chapter_numbers:
        local = local_chapters[no]
        editor_expected = (expected_counts or {}).get(no)
        expected = int(editor_expected) if editor_expected is not None else chapter_len(local.content)
        row = rows.get(no)
        if not row:
            failures[no] = f"列表校验失败：没有在章节管理列表找到第 {no} 章。"
            continue
        actual = row.get("word_count")
        if actual is None:
            failures[no] = f"列表校验失败：第 {no} 章没有读到平台字数。列表行：{row.get('title') or row.get('text') or ''}"
            continue
        actual_int = int(actual)
        delta = abs(actual_int - expected)
        if editor_expected is not None:
            if actual_int != expected:
                failures[no] = (
                    f"列表校验暂未闭环：第 {no} 章编辑器字数 {expected}，"
                    f"章节列表字数 {actual_int}。"
                )
            else:
                log(f"列表校验通过：第 {no} 章编辑器与章节列表均为 {actual_int} 字。")
            continue
        tolerance = word_count_tolerance(expected)
        if not is_platform_count_compatible(actual_int, expected):
            failures[no] = (
                f"列表校验失败：第 {no} 章平台列表字数 {actual}，本地约 {expected}，"
                f"差值 {delta} 超过允许范围。"
                "这通常表示平台列表仍是旧长章，或该章只进入了编辑页/保存了草稿但没有真正确认发布。"
            )
        elif delta > tolerance:
            log(f"列表校验通过：第 {no} 章平台字数 {actual}，本地约 {expected}，差异来自番茄字数统计口径。")
        else:
            log(f"列表校验通过：第 {no} 章平台字数 {actual}，本地约 {expected}。")
    return failures


def wait_for_chapter_list_word_counts(
    page,
    *,
    chapter_manage_url: str,
    local_chapters: dict[int, Chapter],
    chapter_numbers: list[int],
    expected_counts: dict[int, int] | None = None,
    log: Callable[[str], None] = print,
    max_wait_seconds: int = 120,
    interval_seconds: int = 20,
    cancel: CancellationGuard | None = None,
) -> dict[int, str]:
    cancel = cancel or CancellationGuard()
    max_wait_seconds = max(0, int(max_wait_seconds))
    interval_seconds = max(2, int(interval_seconds))
    deadline = time.monotonic() + max_wait_seconds
    attempt = 0
    last_failures: dict[int, str] = {}

    while True:
        cancel.checkpoint()
        attempt += 1
        if attempt == 1:
            log("最终列表校验：同步确认后先刷新章节管理列表；若平台缓存未刷新，会自动等待重试。")
        else:
            log(f"最终列表校验：第 {attempt} 次重试前刷新章节管理列表...")
        try:
            page.goto(chapter_manage_url, wait_until="domcontentloaded", timeout=60000)
            cancel.checkpoint()
            wait_briefly_for_page_ready(page)
        except TaskCancelled:
            raise
        except Exception:

            pass

        failures = verify_chapter_list_word_counts(
            page,
            chapter_manage_url=chapter_manage_url,
            local_chapters=local_chapters,
            chapter_numbers=chapter_numbers,
            expected_counts=expected_counts,
            log=log,
        )
        cancel.checkpoint()
        if not failures:
            if attempt > 1:
                log(f"最终列表校验：等待刷新后通过，共尝试 {attempt} 次。")
            return {}

        last_failures = failures
        now = time.monotonic()
        remaining = deadline - now
        if remaining <= 0:
            log(f"最终列表校验：等待平台列表刷新超时，已尝试 {attempt} 次。")
            return last_failures

        wait_seconds = min(interval_seconds, max(1, int(remaining)))
        failed_numbers = ", ".join(str(no) for no in sorted(failures))
        log(f"最终列表校验暂未通过：第 {failed_numbers} 章列表字数可能还没刷新，等待 {wait_seconds} 秒后重试...")
        try:
            cancel.wait_page(page, wait_seconds * 1000)
        except TaskCancelled:
            raise
        except Exception:
            slept = 0.0
            while slept < wait_seconds:
                cancel.checkpoint()
                current = min(0.2, wait_seconds - slept)
                time.sleep(current)
                slept += current
