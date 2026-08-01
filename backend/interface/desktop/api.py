from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from backend.bootstrap import ApplicationServices, create_application_services
from backend.features.novel_processing.chapter_parser import parse_chapter_source
from backend.features.novel_processing.models import Chapter as PreviewChapter
from backend.infrastructure.desktop.dialogs import (
    open_file,
    open_login_state_dialog,
    open_native_dialog,
    open_path,
    open_source_dialog,
)
from backend.infrastructure.files.storage import atomic_write_text
from backend.infrastructure.persistence.config import deep_update, load_config, save_config, set_config_path
from backend.interface.desktop.events import FrontendBridge
from backend.interface.desktop.tasks import DesktopTaskCoordinator, log_category_for_page
from backend.runtime.data_reset import reset_app_data, reset_login_state
from backend.runtime.jobs.registry import TaskRegistry
from backend.runtime.logging import setup_logging
from backend.runtime.paths import FANQIE_AUTH_STATE_FILE, LOG_FILE, get_state_paths, latest_log_file
from backend.runtime.defaults import DEFAULT_CHAPTER_MANAGE_URL
from backend.platforms.fanqie.actions.interactions import ensure_logged_in, goto_chapter_manage
from backend.platforms.fanqie.book_identity import chapter_manage_book_id, collect_book_manage_entries
from backend.platforms.fanqie.browser.session import BrowserSession, resolve_auth_state_file

FANQIE_TASK_RESOURCE = "fanqie_browser"


def _config_value(config: dict[str, Any], dotted_path: str) -> str:
    value: Any = config
    for part in str(dotted_path or "").split("."):
        if not isinstance(value, dict) or part not in value:
            return ""
        value = value.get(part)
    return str(value or "")


class WebviewApi:
    def __init__(self, services: ApplicationServices | None = None) -> None:
        self._window: Any | None = None
        self._config = load_config()
        self._services = services or create_application_services()
        self._bridge = FrontendBridge()
        self._task_registry = TaskRegistry()
        self._tasks = DesktopTaskCoordinator(self._bridge, registry=self._task_registry)

    def bind_window(self, window: Any) -> None:
        self._window = window
        self._bridge.bind_window(window)

    def get_state(self) -> dict[str, Any]:
        return {
            "config": self._config,
            "recentFiles": [],
            "paths": get_state_paths(),
            "platforms": {"openai": "OpenAI", "local": "本地"},
            "logTail": self._read_log_tail(),
        }

    def save_config(self, config: dict[str, Any] | None) -> bool:
        deep_update(self._config, config or {})
        save_config(self._config)
        return True

    def choose_file(self, config_path: str = "", save: bool = False, save_filename: str = "output.txt") -> str:
        path = open_native_dialog(self._window, save=save, folder=False, save_filename=save_filename)
        return self._remember_path(config_path, path)

    def choose_folder(self, config_path: str = "") -> str:
        path = open_native_dialog(self._window, save=False, folder=True)
        return self._remember_path(config_path, path)

    def choose_source(self, config_path: str = "") -> str:
        current = _config_value(self._config, config_path)
        path = open_source_dialog(self._window, current_path=current)
        return self._remember_path(config_path, path)

    def choose_login_state(self, config_path: str = "") -> str:
        current = _config_value(self._config, config_path)
        path = open_login_state_dialog(self._window, current_path=current)
        return self._remember_path(config_path, path)

    def choose_directory(self, config_path: str = "") -> str:
        return self.choose_folder(config_path)

    def open_path(self, path_key: str) -> bool:
        return open_path(path_key)

    def open_log(self, page: str = "") -> bool:
        category = log_category_for_page(page)
        remembered = self._tasks.latest_log(category)
        if remembered and Path(remembered).exists():
            return open_file(remembered, create=True)
        return open_file(str(latest_log_file(category)), create=True)

    def open_backup(self, path: str = "") -> bool:
        return open_file(path) if path else open_path("data")

    def check_login_state(self) -> bool:
        return FANQIE_AUTH_STATE_FILE.exists()

    def do_login(self) -> dict[str, Any]:
        task_name = "fanqie_login"
        conflict = self._start_fanqie_task(task_name)
        if conflict:
            return conflict
        session: BrowserSession | None = None
        succeeded = False
        try:
            chapter_manage_url = (
                _config_value(self._config, "auto_publish.chapterManageUrl")
                or _config_value(self._config, "chapter_sync.chapterManageUrl")
                or DEFAULT_CHAPTER_MANAGE_URL
            )
            if not chapter_manage_url.startswith("http"):
                return {"ok": False, "message": "请先在发布页或同步页填写章节管理 URL。"}
            session = BrowserSession.open(
                debug_category="auto_publish",
                debug_enabled=False,
                failure_debug_enabled=False,
            )
            page = session.page
            goto_chapter_manage(page, chapter_manage_url)
            ensure_logged_in(
                page,
                chapter_manage_url,
                log=lambda message: self._bridge.emit_log("auto_publish", message),
                wait_for_login=True,
            )
            succeeded = True
            return {"ok": True, "message": "番茄账号登录成功。"}
        except Exception as exc:
            return {"ok": False, "message": f"登录未完成：{exc}"}
        finally:
            if session is not None:
                session.close(save_state=succeeded)
            self._task_registry.finish_task(task_name)

    def import_login_state(self) -> dict[str, Any]:
        selected = open_login_state_dialog(self._window, current_path=str(FANQIE_AUTH_STATE_FILE))
        if not selected:
            return {"ok": False, "message": "未选择登录状态。"}
        source = resolve_auth_state_file(selected)
        if not source.is_file():
            return {"ok": False, "message": "所选位置没有找到 state.json。"}
        task_name = "fanqie_auth_import"
        conflict = self._start_fanqie_task(task_name)
        if conflict:
            return conflict
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("登录状态格式无效")
            if source.resolve() != FANQIE_AUTH_STATE_FILE.resolve():
                atomic_write_text(
                    FANQIE_AUTH_STATE_FILE,
                    json.dumps(data, ensure_ascii=False, indent=2),
                    backup_path=FANQIE_AUTH_STATE_FILE.with_name(f"{FANQIE_AUTH_STATE_FILE.name}.bak"),
                )
            return {"ok": True, "message": "登录状态已导入。"}
        except Exception as exc:
            return {"ok": False, "message": f"导入失败：{exc}"}
        finally:
            self._task_registry.finish_task(task_name)

    def reset_login(self) -> dict[str, Any]:
        task_name = "fanqie_auth_reset"
        conflict = self._start_fanqie_task(task_name)
        if conflict:
            return conflict
        try:
            result = reset_login_state()
            level = "warning" if result.get("ok") else "error"
            self._bridge.emit_log("auto_publish", str(result.get("message") or "已重置授权。"), level)
            return result
        finally:
            self._task_registry.finish_task(task_name)

    def reset_app_data(self) -> dict[str, Any]:
        result = reset_app_data(preserve_auth_state=True)
        setup_logging()
        self._config = load_config()
        level = "success" if result.get("ok") else "error"
        self._bridge.emit_log("auto_publish", str(result.get("message") or "已重置数据。"), level)
        return result

    def auto_publish_list_chapters(self, file_path: str) -> dict[str, Any]:
        return self._list_chapters(file_path)

    def auto_publish_run(self, payload: dict[str, Any]) -> bool:
        profile_error = self._validate_book_profile_payload(payload)
        if profile_error:
            self._bridge.emit_log("auto_publish", profile_error, "warning")
            return False
        if not FANQIE_AUTH_STATE_FILE.is_file():
            self._bridge.emit_log("auto_publish", "请先通过账号登录入口完成番茄登录。", "warning")
            return False
        return self._tasks.start(
            "auto_publish",
            "auto_publish",
            lambda callbacks: self._services.publishing.execute(payload, callbacks),
            resource=FANQIE_TASK_RESOURCE,
        )

    def chapter_sync_list_chapters(self, file_path: str) -> dict[str, Any]:
        return self._list_chapters(file_path)

    def chapter_sync_run(self, payload: dict[str, Any]) -> bool:
        profile_error = self._validate_book_profile_payload(payload)
        if profile_error:
            self._bridge.emit_log("chapter_sync", profile_error, "warning")
            return False
        if not FANQIE_AUTH_STATE_FILE.is_file():
            self._bridge.emit_log("chapter_sync", "请先通过账号登录入口完成番茄登录。", "warning")
            return False
        return self._tasks.start(
            "chapter_sync",
            "chapter_sync",
            lambda callbacks: self._services.syncing.execute(payload, callbacks),
            resource=FANQIE_TASK_RESOURCE,
        )

    def list_fanqie_books(self) -> dict[str, Any]:
        if not FANQIE_AUTH_STATE_FILE.is_file():
            return {"ok": False, "message": "请先登录番茄账号。"}
        task_name = "fanqie_book_list"
        conflict = self._start_fanqie_task(task_name)
        if conflict:
            return conflict
        session: BrowserSession | None = None
        try:
            session = BrowserSession.open(
                debug_category="auto_publish",
                debug_enabled=False,
                failure_debug_enabled=False,
                headless=True,
            )
            books = collect_book_manage_entries(session.page, log=lambda _message: None)
            profiles = self._config.get("bookProfiles")
            existing_by_id = {
                str(item.get("id") or ""): item
                for item in profiles
                if isinstance(item, dict) and item.get("id")
            } if isinstance(profiles, list) else {}
            existing_by_book_id = {
                chapter_manage_book_id(str(item.get("chapterManageUrl") or "")): item
                for item in profiles
                if isinstance(item, dict) and chapter_manage_book_id(str(item.get("chapterManageUrl") or ""))
            } if isinstance(profiles, list) else {}
            old_active = existing_by_id.get(str(self._config.get("activeBookId") or ""), {})
            old_active_book_id = chapter_manage_book_id(str(old_active.get("chapterManageUrl") or ""))
            items = []
            for book in books:
                previous = existing_by_id.get(book["id"]) or existing_by_book_id.get(book["bookId"], {})
                items.append({
                    "id": book["id"],
                    "name": book["name"],
                    "novelFile": str(previous.get("novelFile") or ""),
                    "chapterManageUrl": book["chapterManageUrl"],
                })
            self._config["bookProfiles"] = items
            if old_active_book_id:
                active = next((item for item in items if chapter_manage_book_id(item["chapterManageUrl"]) == old_active_book_id), None)
                if active:
                    self._config["activeBookId"] = active["id"]
                    for section in ("auto_publish", "chapter_sync"):
                        settings = self._config.get(section)
                        if isinstance(settings, dict):
                            settings.update({
                                "bookProfileId": active["id"],
                                "expectedBookName": active["name"],
                                "novelFile": active["novelFile"],
                                "chapterManageUrl": active["chapterManageUrl"],
                            })
            save_config(self._config)
            return {"ok": True, "books": items}
        except Exception as exc:
            return {"ok": False, "message": str(exc)}
        finally:
            if session is not None:
                session.close()
            self._task_registry.finish_task(task_name)

    def select_fanqie_book(self, profile_id: str, novel_file: str = "") -> dict[str, Any]:
        target_id = str(profile_id or "").strip()
        profiles = self._config.get("bookProfiles")
        profile = next(
            (item for item in profiles if isinstance(item, dict) and str(item.get("id") or "") == target_id),
            None,
        ) if isinstance(profiles, list) else None
        if not profile:
            return {"ok": False, "message": "没有找到所选番茄作品。"}
        source = str(novel_file or "").strip()
        if source:
            profile["novelFile"] = source
        self._config["activeBookId"] = target_id
        for section in ("auto_publish", "chapter_sync"):
            settings = self._config.get(section)
            if not isinstance(settings, dict):
                settings = {}
                self._config[section] = settings
            settings.update({
                "bookProfileId": target_id,
                "expectedBookName": str(profile.get("name") or ""),
                "novelFile": str(profile.get("novelFile") or ""),
                "chapterManageUrl": str(profile.get("chapterManageUrl") or ""),
            })
        save_config(self._config)
        return {"ok": True, "profile": profile}

    def auto_publish_stop(self) -> bool:
        return self._tasks.stop("auto_publish", "auto_publish", "已请求终止发布，当前章节结束后会终止。")

    def chapter_sync_stop(self) -> bool:
        return self._tasks.stop("chapter_sync", "chapter_sync", "已请求立即终止同步，正在取消所有章节操作。")

    def auto_publish_pause(self) -> bool:
        return self._tasks.pause("auto_publish", "auto_publish", "已暂缓发布。")

    def auto_publish_resume(self) -> bool:
        return self._tasks.resume("auto_publish", "auto_publish", "已继续发布。")

    def chapter_sync_pause(self) -> bool:
        return self._tasks.pause("chapter_sync", "chapter_sync", "已暂缓同步。")

    def chapter_sync_resume(self) -> bool:
        return self._tasks.resume("chapter_sync", "chapter_sync", "已继续同步。")

    def _list_chapters(self, file_path: str) -> dict[str, Any]:
        try:
            chapters = parse_chapter_source(file_path)
            preview = [
                PreviewChapter(
                    number=chapter.number,
                    title=chapter.subtitle,
                    body=chapter.content,
                    raw_heading=chapter.full_title,
                ).to_preview()
                for chapter in chapters
            ]
            return {"ok": True, "message": f"已识别 {len(chapters)} 个章节。", "chapters": preview}
        except Exception as exc:
            return {"ok": False, "message": str(exc), "chapters": []}

    def _start_fanqie_task(self, task_name: str) -> dict[str, Any] | None:
        if self._task_registry.start_task(task_name, resource=FANQIE_TASK_RESOURCE):
            return None
        blocking_task = self._task_registry.blocking_task(task_name, resource=FANQIE_TASK_RESOURCE)
        return {
            "ok": False,
            "message": f"番茄平台任务 {blocking_task or '未知任务'} 正在运行，请先等待或终止当前任务。",
        }

    def _validate_book_profile_payload(self, payload: dict[str, Any]) -> str:
        profile_id = str(payload.get("bookProfileId") or "")
        profiles = self._config.get("bookProfiles")
        profile = next(
            (item for item in profiles if isinstance(item, dict) and str(item.get("id") or "") == profile_id),
            None,
        ) if isinstance(profiles, list) else None
        if not profile:
            return "书籍安全校验失败：当前任务没有对应的已保存书籍配置，已禁止执行。"
        expected = {
            "expectedBookName": str(profile.get("name") or ""),
            "novelFile": str(profile.get("novelFile") or ""),
            "chapterManageUrl": str(profile.get("chapterManageUrl") or ""),
        }
        if any(str(payload.get(key) or "") != value for key, value in expected.items()):
            return "书籍安全校验失败：书名、本地文件或章节 URL 已改动但尚未保存，已禁止执行。"
        return ""

    def _remember_path(self, config_path: str, path: str) -> str:
        if path and config_path:
            set_config_path(self._config, config_path, path)
            save_config(self._config)
        return path

    def _read_log_tail(self, limit: int = 3500) -> str:
        try:
            return LOG_FILE.read_text(encoding="utf-8", errors="ignore")[-limit:] if LOG_FILE.exists() else ""
        except Exception:
            return ""


NovelToolsApi = WebviewApi

__all__ = ["WebviewApi", "NovelToolsApi"]
