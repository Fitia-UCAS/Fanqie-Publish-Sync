from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from backend.infrastructure.serialization.json import to_json_safe
from backend.interface.desktop.events import FrontendBridge
from backend.runtime.jobs.callbacks import TaskCallbacks
from backend.runtime.jobs.registry import TaskRegistry
from backend.runtime.jobs.results import TaskResult
from backend.runtime.logging import get_logger
from backend.runtime.paths import task_log_file

LOGGER = get_logger(__name__)


class DesktopTaskCoordinator:
    def __init__(self, bridge: FrontendBridge, registry: TaskRegistry | None = None) -> None:
        self._bridge = bridge
        self._registry = registry or TaskRegistry()
        self._latest_logs: dict[str, str] = {}

    def start(
        self,
        task_name: str,
        page: str,
        worker: Callable[[TaskCallbacks], TaskResult | dict[str, Any]],
        *,
        resource: str | None = None,
    ) -> bool:
        if not self._registry.start_task(task_name, resource=resource):
            blocking_task = self._registry.blocking_task(task_name, resource=resource)
            message = (
                f"任务 {blocking_task} 正在占用番茄平台，请先等待或终止当前任务。"
                if blocking_task
                else "任务正在运行，请稍候。"
            )
            self._bridge.emit_log(page, message, "warning")
            return False
        thread = threading.Thread(target=self._run, args=(task_name, page, worker), daemon=True)
        thread.start()
        return True

    def stop(self, task_name: str, page: str, message: str) -> bool:
        if not self._registry.request_stop(task_name):
            self._bridge.emit_log(page, "当前没有正在运行的任务。", "warning")
            return False
        self._bridge.emit_log(page, message, "warning")
        return True

    def pause(self, task_name: str, page: str, message: str) -> bool:
        if not self._registry.request_pause(task_name):
            self._bridge.emit_log(page, "当前没有正在运行的任务。", "warning")
            return False
        self._bridge.emit_log(page, message, "warning")
        return True

    def resume(self, task_name: str, page: str, message: str) -> bool:
        if not self._registry.request_resume(task_name):
            self._bridge.emit_log(page, "当前没有正在运行的任务。", "warning")
            return False
        self._bridge.emit_log(page, message, "success")
        return True

    def latest_log(self, category: str) -> str:
        return self._latest_logs.get(category, "")

    def _run(
        self,
        task_name: str,
        page: str,
        worker: Callable[[TaskCallbacks], TaskResult | dict[str, Any]],
    ) -> None:
        category = log_category_for_page(page)
        log_path = None if page in {"auto_publish", "chapter_sync"} else task_log_file(category)
        if log_path:
            self._latest_logs[category] = str(log_path)
            self._append(log_path, f"任务：{task_name}\n开始：{datetime.now():%Y-%m-%d %H:%M:%S}\n")

        def emit_log(message: str, level: str = "info") -> None:
            if log_path:
                self._append(log_path, f"[{datetime.now():%H:%M:%S}] [{level}] {message}\n")
            self._bridge.emit_log(page, message, level)

        callbacks = TaskCallbacks(
            log=emit_log,
            progress=lambda current, total: self._bridge.emit_progress(page, current, total),
            should_stop=lambda: self._registry.is_stop_requested(task_name),
            should_pause=lambda: self._registry.is_pause_requested(task_name),
            event=self._bridge.emit_event,
        )
        try:
            result = worker(callbacks)
            payload = result.to_dict() if isinstance(result, TaskResult) else dict(result)
            safe_payload = to_json_safe(payload)
            if log_path:
                self._append(log_path, f"结束：{safe_payload.get('message') or ''}\n")
            self._bridge.emit_done(page, bool(safe_payload.get("ok")), safe_payload)
        except Exception as exc:
            LOGGER.exception("Task failed: %s", task_name)
            if log_path:
                self._append(log_path, f"异常：{exc}\n")
            self._bridge.emit_log(page, str(exc), "error")
            self._bridge.emit_done(page, False, {"ok": False, "message": str(exc)})
        finally:
            self._registry.finish_task(task_name)

    @staticmethod
    def _append(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(text)


def log_category_for_page(page: str) -> str:
    normalized = str(page or "").strip()
    return {
        "auto_publish": "auto_publish",
        "chapter_sync": "chapter_sync",
    }.get(normalized, "system")
