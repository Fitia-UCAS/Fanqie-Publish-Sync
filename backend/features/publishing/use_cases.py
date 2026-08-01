from __future__ import annotations

from typing import Any, Callable

from backend.features.task_models import PublishTaskPayload
from backend.features.task_support import resolve_chapter_source, result_to_dict
from backend.platforms.fanqie.publishing.service import run_multi_chapter_publish
from backend.runtime.jobs.callbacks import TaskCallbacks
from backend.runtime.jobs.results import TaskResult
from backend.runtime.run_logs.fanqie import FanqieTaskLog


class PublishChapters:
    def __init__(self, runner: Callable[..., list[Any]] = run_multi_chapter_publish) -> None:
        self._runner = runner

    def execute(self, payload: dict[str, Any], callbacks: TaskCallbacks | None = None) -> TaskResult:
        callbacks = callbacks or TaskCallbacks()
        request = PublishTaskPayload.model_validate(payload)
        source = resolve_chapter_source(request.novel_file)
        url = request.chapter_manage_url.strip()
        if not url.startswith("http"):
            return TaskResult(False, "请填写番茄章节管理 URL。")
        expected_book_name = request.expected_book_name.strip()
        if not request.book_profile_id.strip() or not expected_book_name:
            return TaskResult(False, "请先选择并保存书籍配置；发布前必须明确对应的番茄作品名。")
        start, end = request.chapter_range
        chapters = list(range(start, end + 1))
        task_log = FanqieTaskLog(
            callbacks=callbacks,
            task_kind="auto_publish",
            operation="publish",
            start=start,
            end=end,
            total=len(chapters),
        )
        task_log.emit_start("publish", start, end)
        results = self._runner(
            novel_file=source,
            chapters=chapters,
            chapter_manage_url=url,
            expected_book_name=expected_book_name,
            use_ai=request.use_ai,
            verify_after_publish=request.verify_after_publish,
            debug_screenshots=request.debug_screenshots,
            failure_screenshots=request.failure_screenshots,
            browser_headless=request.browser_headless,
            clear_author_note=request.clear_author_note,
            git_tracking=request.git_tracking,
            auth_state_path=request.auth_state_path,
            manual_schedule_enabled=request.manual_schedule,
            schedule_start_date=request.schedule_start_date,
            schedule_morning_time=request.schedule_morning_time,
            schedule_morning_count=request.schedule_morning_count,
            schedule_afternoon_time=request.schedule_afternoon_time,
            schedule_afternoon_count=request.schedule_afternoon_count,
            log=task_log.log,
            stop_requested=callbacks.stop_requested,
            pause_requested=callbacks.pause_requested,
        )
        ok_count = sum(1 for item in results if getattr(item, "ok", False))
        task_log.finish(ok_count, len(results))
        stopped = callbacks.stop_requested()
        message = f"已终止发布：成功 {ok_count}/{len(chapters)}。" if stopped else f"任务结束：成功 {ok_count}/{len(chapters)}。"
        return TaskResult(
            (not stopped) and ok_count == len(chapters),
            message,
            path=task_log.path,
            data={"items": [result_to_dict(item) for item in results], "stopped": stopped},
        )
