from __future__ import annotations

from typing import Any, Callable

from backend.features.task_models import SyncTaskPayload
from backend.features.task_support import resolve_chapter_source, result_to_dict
from backend.platforms.fanqie.syncing.service import run_multi_chapter_sync
from backend.runtime.jobs.callbacks import TaskCallbacks
from backend.runtime.jobs.results import TaskResult
from backend.runtime.run_logs.fanqie import FanqieTaskLog


class SyncChapters:
    def __init__(self, runner: Callable[..., list[Any]] = run_multi_chapter_sync) -> None:
        self._runner = runner

    def execute(self, payload: dict[str, Any], callbacks: TaskCallbacks | None = None) -> TaskResult:
        callbacks = callbacks or TaskCallbacks()
        request = SyncTaskPayload.model_validate(payload)
        source = resolve_chapter_source(request.novel_file)
        url = request.chapter_manage_url.strip()
        if not url.startswith("http"):
            return TaskResult(False, "请填写番茄章节管理 URL。")
        operation = request.operation
        task_kind = request.task_kind
        chapters = request.chapters
        start, end = min(chapters), max(chapters)
        task_log = FanqieTaskLog(
            callbacks=callbacks,
            task_kind=task_kind,
            operation=operation,
            start=start,
            end=end,
            total=len(chapters),
            chapters=chapters if request.has_explicit_chapters else None,
        )
        task_log.emit_start(operation, start, end, chapters=chapters if request.has_explicit_chapters else None)
        results = self._runner(
            novel_file=source,
            chapters=chapters,
            chapter_manage_url=url,
            use_ai=request.use_ai,
            check_only=False,
            direction=request.direction,
            log=task_log.log,
            verify_after_publish=request.verify_after_publish,
            debug_screenshots=request.debug_screenshots,
            failure_screenshots=request.failure_screenshots,
            git_tracking=request.git_tracking,
            auth_state_path=request.auth_state_path,
            manual_schedule_enabled=request.manual_schedule,
            schedule_start_date=request.schedule_start_date,
            schedule_morning_time=request.schedule_morning_time,
            schedule_morning_count=request.schedule_morning_count,
            schedule_afternoon_time=request.schedule_afternoon_time,
            schedule_afternoon_count=request.schedule_afternoon_count,
            stop_requested=callbacks.stop_requested,
            pause_requested=callbacks.pause_requested,
        )
        ok_count = sum(1 for item in results if getattr(item, "ok", False))
        task_log.finish(ok_count, len(results))
        stopped = callbacks.stop_requested()
        message = f"已终止同步：成功 {ok_count}/{len(chapters)}。" if stopped else f"任务结束：成功 {ok_count}/{len(chapters)}。"
        return TaskResult(
            (not stopped) and ok_count == len(chapters),
            message,
            path=task_log.path,
            data={"items": [result_to_dict(item) for item in results], "stopped": stopped},
        )
