from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import replace
from pathlib import Path
from threading import Lock
from typing import Callable

from backend.platforms.fanqie.syncing.local_source import Chapter, get_local_chapter, parse_chapters
from backend.runtime.errors import ErrorStage, TaskCancelled
from backend.runtime.jobs.cancellation import CancellationGuard
from backend.features.syncing.models import ChapterSyncOptions, ChapterSyncResult
from backend.features.syncing.options import make_chapter_sync_options
from backend.platforms.fanqie.syncing.single import run_single_chapter_sync
from backend.platforms.fanqie.syncing.preflight import wait_for_chapter_list_word_counts
from backend.platforms.fanqie.browser.session import BrowserSession, save_failure_debug
from backend.platforms.fanqie.actions.interactions import dismiss_popups, goto_chapter_manage
from backend.platforms.fanqie.pages.chapter_list import build_chapter_editor_index
from backend.platforms.fanqie.models import build_schedule_slots, describe_schedule_slots
from backend.features.novel_processing.chapter_parser import chapters_by_number
from backend.runtime.defaults import DEFAULT_CHAPTER_MANAGE_URL
from backend.platforms.fanqie.content_verification import verify_remote_content_matches
from backend.platforms.fanqie.book_identity import verify_chapter_manage_book
from backend.platforms.fanqie.pages.editor import RetryableEditorError


def run_multi_chapter_sync(
    novel_file: Path,
    chapters: list[int],
    chapter_manage_url: str = DEFAULT_CHAPTER_MANAGE_URL,
    expected_book_name: str = "",
    use_ai: bool = False,
    check_only: bool = False,
    direction: str = "local_to_remote",
    log: Callable[[str], None] = print,
    verify_after_publish: bool = True,
    debug_screenshots: bool = True,
    failure_screenshots: bool = True,
    browser_headless: bool = True,
    git_tracking: bool = True,
    auth_state_path: str = "",
    concurrency: int = 2,
    clear_author_note: bool = False,
    manual_schedule_enabled: bool = False,
    schedule_start_date: str = "",
    schedule_morning_time: str = "10:00",
    schedule_morning_count: int = 1,
    schedule_afternoon_time: str = "18:00",
    schedule_afternoon_count: int = 0,
    stop_requested: Callable[[], bool] | None = None,
    pause_requested: Callable[[], bool] | None = None,
) -> list[ChapterSyncResult]:
    options = make_chapter_sync_options(
        chapter_manage_url=chapter_manage_url,
        use_ai=use_ai,
        check_only=check_only,
        direction=direction,
        verify_after_publish=verify_after_publish,
        debug_screenshots=debug_screenshots,
        failure_screenshots=failure_screenshots,
        browser_headless=browser_headless,
        git_tracking=git_tracking,
        auth_state_path=auth_state_path,
        concurrency=concurrency,
        clear_author_note=clear_author_note,
        schedule_slots=build_schedule_slots(
            chapters,
            enabled=manual_schedule_enabled and direction == "local_to_remote" and not check_only,
            start_date=schedule_start_date,
            morning_time=schedule_morning_time,
            morning_count=schedule_morning_count,
            afternoon_time=schedule_afternoon_time,
            afternoon_count=schedule_afternoon_count,
        ),
    )
    if options.debug_screenshots:
        log("番茄同步调试截图已开启。")
    else:
        log("番茄同步调试截图已关闭。")
    if options.git_tracking:
        log("番茄同步 Git 追踪已开启。")
    else:
        log("番茄同步 Git追踪已关闭。")
    schedule_desc = describe_schedule_slots(options.schedule_slots)
    if schedule_desc:
        log(schedule_desc)

    session = BrowserSession.open(
        debug_category="chapter_sync",
        debug_enabled=options.debug_screenshots,
        failure_debug_enabled=options.failure_screenshots,
        auth_state_path=options.auth_state_path,
        headless=options.browser_headless,
    )
    page = session.page
    state = MultiChapterSyncState(chapters=list(chapters), results=[], result_chapter_numbers=[])
    cancel = CancellationGuard(stop_requested)
    log_lock = Lock()

    def synchronized_log(message: str) -> None:
        with log_lock:
            log(message)

    try:
        cancel.checkpoint()
        if options.browser_headless:
            synchronized_log("同步浏览器已静默运行，不会弹出网页窗口。")
        else:
            synchronized_log("同步浏览器窗口已显示，可用于观察和排错。")
        verify_chapter_manage_book(page, chapter_manage_url, expected_book_name, log=synchronized_log)
        local_chapters = _local_chapters_by_number(novel_file, chapters)
        synchronized_log("正文实时读取已启用：每章操作前都会重新读取本地小说来源。")
        if options.direction == "local_to_remote":
            synchronized_log(
                "本地强制覆盖已启用：编辑页可能残留旧草稿，每章都会重新写入本地标题和完整正文后再提交。"
            )

        editor_url_cache = _index_editors_if_needed(
            page,
            chapter_manage_url=chapter_manage_url,
            chapters=chapters,
            editor_url_cache={},
            log=synchronized_log,
        )
        if not chapters:
            synchronized_log("没有需要处理的章节。")

        parallel_chapters, serial_chapters = _split_parallel_chapters(
            chapters=chapters,
            options=options,
            editor_url_cache=editor_url_cache,
        )
        chapters_without_editor = list(serial_chapters)
        if parallel_chapters and options.concurrency > 1:
            synchronized_log(
                f"受控并发同步已启用：{min(options.concurrency, len(parallel_chapters))} 路；"
                "每路使用独立浏览器会话，最多同时处理 4 章。"
            )
            retry_serially = _process_indexed_chapters_concurrently(
                novel_file=novel_file,
                chapters=parallel_chapters,
                base_options=options,
                editor_url_cache=editor_url_cache,
                state=state,
                log=synchronized_log,
                cancel=cancel,
                pause_requested=pause_requested,
            )
            if retry_serially:
                retry_set = set(retry_serially)
                retry_serially = [chapter_no for chapter_no in chapters if chapter_no in retry_set]
                serial_set = set(serial_chapters)
                serial_chapters = [
                    chapter_no
                    for chapter_no in chapters
                    if chapter_no in retry_set or chapter_no in serial_set
                ]
                synchronized_log(
                    "并发编辑器未稳定或尚未启动的章节将自动改用单路处理："
                    + "、".join(f"第 {chapter_no} 章" for chapter_no in retry_serially)
                )
        else:
            serial_chapters = chapters

        if serial_chapters and not cancel.requested():
            if parallel_chapters and chapters_without_editor:
                synchronized_log("没有直接编辑入口的章节将改为串行处理，避免并发新建造成章节错位。")
            _process_chapters(
                page=page,
                novel_file=novel_file,
                chapters=serial_chapters,
                local_chapters=local_chapters,
                base_options=options,
                editor_url_cache=editor_url_cache,
                state=state,
                log=synchronized_log,
                stop_requested=stop_requested,
                pause_requested=pause_requested,
                cancel=cancel,
            )
        if not _stop_requested(stop_requested):
            _final_list_verify_if_needed(
                page=page,
                options=options,
                chapter_manage_url=chapter_manage_url,
                local_chapters=local_chapters,
                chapters=chapters,
                novel_file=novel_file,
                state=state,
                log=synchronized_log,
                cancel=cancel,
            )
        return state.results
    except TaskCancelled:
        synchronized_log("已立即终止同步，所有活动章节正在退出。")
        return state.results
    finally:
        session.close()


class MultiChapterSyncState:
    def __init__(self, chapters: list[int], results: list[ChapterSyncResult], result_chapter_numbers: list[int]) -> None:
        self.chapters = chapters
        self.results = results
        self.result_chapter_numbers = result_chapter_numbers

    def append(self, chapter_no: int, result: ChapterSyncResult) -> None:
        self.results.append(result)
        self.result_chapter_numbers.append(chapter_no)


def _local_chapters_by_number(novel_file: Path, chapters: list[int]) -> dict[int, Chapter]:
    local_chapters = chapters_by_number(parse_chapters(novel_file), "本地小说来源")
    missing_local = [no for no in chapters if no not in local_chapters]
    if missing_local:
        raise RuntimeError(f"本地小说来源中没有找到章节：{', '.join(str(no) for no in missing_local)}")
    return local_chapters


def _index_editors_if_needed(
    page,
    *,
    chapter_manage_url: str,
    chapters: list[int],
    editor_url_cache: dict[int, str],
    log: Callable[[str], None],
) -> dict[int, str]:
    if editor_url_cache:
        log(f"章节入口索引：已复用 {len(editor_url_cache)} 个章节入口。")
        return editor_url_cache
    try:
        editor_url_cache = build_chapter_editor_index(page, chapter_manage_url, chapters, log=log)
        if editor_url_cache:
            log(f"章节入口索引：已缓存 {len(editor_url_cache)} 个章节入口，后续会减少重复翻页定位。")
    except Exception as exc:
        log(f"章节入口索引建立失败，自动降级为常规定位：{exc}")
        editor_url_cache = {}
    return editor_url_cache


def _split_parallel_chapters(
    *,
    chapters: list[int],
    options: ChapterSyncOptions,
    editor_url_cache: dict[int, str],
) -> tuple[list[int], list[int]]:
    parallel_allowed = (
        options.is_publish_to_remote
        and options.concurrency > 1
        and not options.schedule_slots
    )
    if not parallel_allowed:
        return [], list(chapters)
    parallel = [chapter_no for chapter_no in chapters if editor_url_cache.get(chapter_no)]
    serial = [chapter_no for chapter_no in chapters if chapter_no not in set(parallel)]
    return parallel, serial


def _process_indexed_chapters_concurrently(
    *,
    novel_file: Path,
    chapters: list[int],
    base_options: ChapterSyncOptions,
    editor_url_cache: dict[int, str],
    state: MultiChapterSyncState,
    log: Callable[[str], None],
    cancel: CancellationGuard,
    pause_requested: Callable[[], bool] | None = None,
) -> list[int]:
    worker_count = max(1, min(4, int(base_options.concurrency), len(chapters)))
    per_chapter_options = (
        replace(base_options, verify_after_publish=False)
        if base_options.should_final_list_verify
        else base_options
    )
    pending: dict[Future[ChapterSyncResult], int] = {}
    next_index = 0
    completed = 0
    retry_serially: list[int] = []
    scheduling_stopped = False

    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="fanqie-sync") as executor:
        try:
            while pending or next_index < len(chapters):
                cancel.checkpoint()
                if pause_requested and pause_requested() and not pending:
                    _wait_while_paused(
                        pause_requested=pause_requested,
                        stop_requested=cancel.requested,
                        log=log,
                        label="同步",
                    )
                    cancel.checkpoint()

                while (
                    next_index < len(chapters)
                    and len(pending) < worker_count
                    and not scheduling_stopped
                    and not (pause_requested and pause_requested())
                ):
                    chapter_no = chapters[next_index]
                    next_index += 1
                    log(f"并发任务启动：第 {chapter_no} 章（{next_index}/{len(chapters)}）")
                    future = executor.submit(
                        _run_indexed_chapter_worker,
                        novel_file=novel_file,
                        chapter_no=chapter_no,
                        options=per_chapter_options,
                        editor_url=editor_url_cache[chapter_no],
                        log=log,
                        cancel=cancel,
                    )
                    pending[future] = chapter_no

                if not pending:
                    continue
                done, _not_done = wait(tuple(pending), timeout=0.2, return_when=FIRST_COMPLETED)
                for future in done:
                    chapter_no = pending.pop(future)
                    try:
                        result = future.result()
                    except TaskCancelled:
                        raise
                    if _is_retryable_parallel_result(result):
                        retry_serially.append(chapter_no)
                        if not scheduling_stopped:
                            scheduling_stopped = True
                            deferred = chapters[next_index:]
                            if deferred:
                                retry_serially.extend(deferred)
                                next_index = len(chapters)
                                log(
                                    "检测到平台编辑器加载拥塞，已停止启动新的并发任务；"
                                    f"剩余 {len(deferred)} 章将改用单路处理。"
                                )
                    else:
                        state.append(chapter_no, result)
                    completed += 1
                    log(f"并发进度：第 {chapter_no} 章已结束（{completed}/{len(chapters)}）")
        except TaskCancelled:
            for future in pending:
                future.cancel()
            raise
    return retry_serially


def _run_indexed_chapter_worker(
    *,
    novel_file: Path,
    chapter_no: int,
    options: ChapterSyncOptions,
    editor_url: str,
    log: Callable[[str], None],
    cancel: CancellationGuard,
) -> ChapterSyncResult:
    session = None

    def chapter_log(message: str) -> None:
        log(f"[第 {chapter_no} 章] {message}")

    try:
        cancel.checkpoint()
        session = BrowserSession.open(
            debug_category="chapter_sync",
            debug_enabled=options.debug_screenshots,
            failure_debug_enabled=options.failure_screenshots,
            auth_state_path=options.auth_state_path,
            headless=options.browser_headless,
        )
        cancel.checkpoint()
        local_chapter = get_local_chapter(novel_file, chapter_no)
        return run_single_chapter_sync(
            page=session.page,
            novel_file=novel_file,
            chapter_no=chapter_no,
            options=options,
            log=chapter_log,
            local_chapter=local_chapter,
            editor_url_cache={chapter_no: editor_url},
            created_chapter_numbers=set(),
            cancel=cancel,
        )
    except TaskCancelled:
        raise
    except Exception as exc:
        if session is not None:
            save_failure_debug(session.page, f"chapter_{chapter_no:03d}_failed")
        retryable = isinstance(exc, RetryableEditorError)
        msg = (
            f"并发尝试未稳定：第 {chapter_no} 章｜{exc}；将转入单路处理。"
            if retryable
            else f"失败：第 {chapter_no} 章｜{exc}"
        )
        chapter_log(msg)
        return ChapterSyncResult(
            ok=False,
            changed=False,
            published=False,
            message=msg,
            error_stage=ErrorStage.EDITOR if retryable else ErrorStage.CHAPTER,
        )
    finally:
        if session is not None:
            session.close(save_state=False)


def _process_chapters(
    *,
    page,
    novel_file: Path,
    chapters: list[int],
    local_chapters: dict[int, Chapter],
    base_options: ChapterSyncOptions,
    editor_url_cache: dict[int, str],
    state: MultiChapterSyncState,
    log: Callable[[str], None],
    stop_requested: Callable[[], bool] | None = None,
    pause_requested: Callable[[], bool] | None = None,
    cancel: CancellationGuard | None = None,
) -> None:
    cancel = cancel or CancellationGuard(stop_requested)
    process_total = len(chapters)
    created_chapter_numbers: set[int] = set()
    per_chapter_options = (
        replace(base_options, verify_after_publish=False)
        if base_options.should_final_list_verify
        else base_options
    )
    for index, chapter_no in enumerate(chapters, start=1):
        cancel.checkpoint()
        _wait_while_paused(pause_requested=pause_requested, stop_requested=stop_requested, log=log, label="同步")
        cancel.checkpoint()
        log(f"后台批量处理：第 {chapter_no} 章（{index}/{process_total}）")
        max_attempts = 2 if base_options.is_publish_to_remote and editor_url_cache.get(chapter_no) else 1
        for attempt in range(1, max_attempts + 1):
            try:
                local_chapter = get_local_chapter(novel_file, chapter_no)
                local_chapters[chapter_no] = local_chapter
                result = run_single_chapter_sync(
                    page=page,
                    novel_file=novel_file,
                    chapter_no=chapter_no,
                    options=per_chapter_options,
                    log=log,
                    local_chapter=local_chapter,
                    editor_url_cache=editor_url_cache,
                    created_chapter_numbers=created_chapter_numbers,
                    cancel=cancel,
                )
                state.append(chapter_no, result)
                break
            except TaskCancelled:
                raise
            except RetryableEditorError as exc:
                if attempt < max_attempts:
                    log(f"第 {chapter_no} 章单路编辑器仍未稳定，将重新打开本章再试一次：{exc}")
                    cancel.wait_page(page, 750)
                    continue
                _record_chapter_failure(
                    page=page,
                    chapter_manage_url=base_options.chapter_manage_url,
                    chapter_no=chapter_no,
                    exc=exc,
                    state=state,
                    log=log,
                )
                break
            except Exception as exc:
                _record_chapter_failure(
                    page=page,
                    chapter_manage_url=base_options.chapter_manage_url,
                    chapter_no=chapter_no,
                    exc=exc,
                    state=state,
                    log=log,
                )
                break


def _record_chapter_failure(*, page, chapter_manage_url: str, chapter_no: int, exc: Exception, state: MultiChapterSyncState, log: Callable[[str], None]) -> None:
    save_failure_debug(page, f"chapter_{chapter_no:03d}_failed")
    msg = f"失败：第 {chapter_no} 章｜{exc}"
    log(msg)
    error_stage = ErrorStage.EDITOR if isinstance(exc, RetryableEditorError) else ErrorStage.CHAPTER
    state.append(chapter_no, ChapterSyncResult(ok=False, changed=False, published=False, message=msg, error_stage=error_stage))
    try:
        goto_chapter_manage(page, chapter_manage_url)
        dismiss_popups(page)
    except Exception:
        pass


def _final_list_verify_if_needed(
    *,
    page,
    options: ChapterSyncOptions,
    chapter_manage_url: str,
    local_chapters: dict[int, Chapter],
    chapters: list[int],
    novel_file: Path,
    state: MultiChapterSyncState,
    log: Callable[[str], None],
    cancel: CancellationGuard | None = None,
) -> None:
    cancel = cancel or CancellationGuard()
    cancel.checkpoint()
    if not options.should_final_list_verify:
        return
    chapter_numbers = [
        no
        for no, result in zip(state.result_chapter_numbers, state.results)
        if result.ok and result.published
    ]
    if not chapter_numbers:
        log("最终列表校验：没有已提交成功的章节需要校验。")
        return
    latest_local_chapters = _local_chapters_by_number(novel_file, chapter_numbers)
    local_chapters.update(latest_local_chapters)
    result_by_chapter = {
        no: result
        for no, result in zip(state.result_chapter_numbers, state.results)
        if no in chapter_numbers
    }
    expected_counts = {
        no: result.platform_editor_count
        for no, result in result_by_chapter.items()
        if result.platform_editor_count is not None
    }
    log("正在进行最终章节列表校验，确认已发布列表字数是否全部更新...")
    failures = wait_for_chapter_list_word_counts(
        page,
        chapter_manage_url=chapter_manage_url,
        local_chapters=local_chapters,
        chapter_numbers=chapter_numbers,
        expected_counts=expected_counts,
        log=log,
        cancel=cancel,
    )
    for no in list(failures):
        cancel.checkpoint()
        content_failure = verify_remote_content_matches(
            page,
            chapter_no=no,
            chapter_manage_url=chapter_manage_url,
            local=local_chapters[no],
            log=log,
            cancel=cancel,
        )
        if content_failure is None:
            failures.pop(no, None)
        else:
            failures[no] = content_failure
    if failures:
        _mark_list_verify_failures(failures=failures, state=state, log=log)
    else:
        failed_count = sum(1 for result in state.results if not result.ok)
        if failed_count:
            log(
                f"成功章节最终校验通过：已提交成功的 {len(chapter_numbers)} 章均完成闭环；"
                f"整体任务仍有 {failed_count} 章失败。"
            )
        else:
            log("最终同步校验通过：平台列表字数已闭环，或平台最新正文已与本地完全一致。")


def _mark_list_verify_failures(*, failures: dict[int, str], state: MultiChapterSyncState, log: Callable[[str], None]) -> None:
    for no, reason in failures.items():
        log(f"失败：第 {no} 章｜{reason}")
        for index, chapter in enumerate(state.result_chapter_numbers):
            if chapter == no and index < len(state.results):
                state.results[index].ok = False
                state.results[index].message = reason
                state.results[index].error_stage = ErrorStage.LIST_VERIFY
                break


def _is_retryable_parallel_result(result: ChapterSyncResult) -> bool:
    return not result.ok and result.error_stage == ErrorStage.EDITOR


def _stop_requested(stop_requested: Callable[[], bool] | None) -> bool:
    return bool(stop_requested and stop_requested())


def _wait_while_paused(
    *,
    pause_requested: Callable[[], bool] | None,
    stop_requested: Callable[[], bool] | None,
    log: Callable[[str], None],
    label: str,
) -> None:
    announced = False
    import time
    while pause_requested and pause_requested():
        if _stop_requested(stop_requested):
            return
        if not announced:
            log(f"{label}已暂缓，点击继续后会处理下一章。")
            announced = True
        time.sleep(0.5)
