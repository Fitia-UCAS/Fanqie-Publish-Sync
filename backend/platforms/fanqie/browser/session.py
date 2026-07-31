from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path
from typing import Any, ClassVar

from backend.infrastructure.files.storage import atomic_write_text
from backend.runtime.logging import get_logger
from backend.runtime.paths import (
    BROWSER_DATA_DIR,
    CHAPTER_SYNC_DEBUG_DIR,
    FANQIE_ACCOUNTS_FILE,
    FANQIE_ACCOUNT_STATES_DIR,
    FANQIE_AUTH_STATE_FILE,
    PUBLISH_DEBUG_DIR,
)
from backend.runtime.settings import RuntimeSettings

Page = Any

_DEBUG_COUNTER = count(1)
LOGGER = get_logger(__name__)


@dataclass(slots=True)
class DebugCapture:
    category: str
    enabled: bool
    failure_enabled: bool
    dedupe_enabled: bool
    fingerprints: set[str] = field(default_factory=set)

    def save(self, page: Page, name: str, *, force: bool = False) -> None:
        if not self.enabled:
            return
        _write_debug_image(page, name, capture=self, force=force)

    def save_failure(self, page: Page, name: str) -> None:
        if self.failure_enabled:
            _write_debug_image(page, name, capture=self, force=True)


@dataclass(slots=True)
class BrowserSession:
    playwright: Any
    browser: Any
    context: Any
    page: Page
    auth_state_file: Path
    debug_capture: DebugCapture
    _closed: bool = False

    _sessions_by_context: ClassVar[dict[int, "BrowserSession"]] = {}

    @classmethod
    def open(
        cls,
        *,
        debug_category: str = "chapter_sync",
        debug_enabled: bool | None = None,
        failure_debug_enabled: bool | None = None,
        auth_state_path: str | Path | None = None,
        settings: RuntimeSettings | None = None,
        headless: bool = False,
    ) -> "BrowserSession":
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise RuntimeError("缺少依赖：playwright。请先执行：pip install -r requirements.txt") from exc

        playwright = sync_playwright().start()
        BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        browser_args = ["--disable-blink-features=AutomationControlled"]
        if not headless:
            browser_args.append("--start-maximized")
        launch_kwargs: dict[str, Any] = {"headless": bool(headless), "args": browser_args}
        context_kwargs: dict[str, Any] = (
            {"viewport": {"width": 1920, "height": 1080}} if headless else {"no_viewport": True}
        )
        auth_state_file = resolve_auth_state_file(auth_state_path)
        if auth_state_file.exists():
            context_kwargs["storage_state"] = str(auth_state_file)

        try:
            runtime_settings = settings or RuntimeSettings.from_environment()
            browser = launch_system_browser(
                playwright,
                launch_kwargs,
                browser_channel=runtime_settings.browser_channel,
            )
            context = browser.new_context(**context_kwargs)
        except Exception as exc:
            playwright.stop()
            raise RuntimeError(
                "浏览器启动失败。当前版本默认使用系统 Microsoft Edge 或 Google Chrome，不再下载 Playwright Chromium；"
                "如果浏览器被占用，请先关闭自动化打开的窗口后重试。"
            ) from exc

        page = context.pages[0] if context.pages else context.new_page()
        category = debug_category or "chapter_sync"
        capture = DebugCapture(
            category=category,
            enabled=_default_debug_enabled(category) if debug_enabled is None else bool(debug_enabled),
            failure_enabled=True if failure_debug_enabled is None else bool(failure_debug_enabled),
            dedupe_enabled=_debug_dedupe_enabled(category),
        )
        session = cls(
            playwright=playwright,
            browser=browser,
            context=context,
            page=page,
            auth_state_file=auth_state_file,
            debug_capture=capture,
        )
        cls._sessions_by_context[id(context)] = session
        if not headless:
            maximize_page_window(page)
        try:
            page.wait_for_timeout(300)
        except Exception:
            pass
        return session

    @classmethod
    def for_page(cls, page: Page) -> "BrowserSession | None":
        try:
            return cls._sessions_by_context.get(id(page.context))
        except Exception:
            return None

    def close(self, *, save_state: bool = True) -> None:
        if self._closed:
            return
        self._closed = True
        if save_state:
            self._save_auth_state()
        self._sessions_by_context.pop(id(self.context), None)
        try:
            self.context.close()
        except Exception:
            pass
        try:
            self.browser.close()
        except Exception:
            pass
        try:
            self.playwright.stop()
        except Exception:
            pass

    def _save_auth_state(self) -> None:
        try:
            self.auth_state_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                state = self.context.storage_state(indexed_db=True)
            except TypeError:
                state = self.context.storage_state()
            atomic_write_text(
                self.auth_state_file,
                json.dumps(state, ensure_ascii=False, indent=2),
                backup_path=self.auth_state_file.with_name(f"{self.auth_state_file.name}.bak"),
            )
        except Exception:
            LOGGER.exception("保存番茄登录状态失败：%s", self.auth_state_file)

    def __enter__(self) -> "BrowserSession":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


def launch_system_browser(
    playwright: Any,
    launch_kwargs: dict[str, Any],
    *,
    browser_channel: str,
):
    configured_channel = (browser_channel or "").strip()
    channels: list[str] = []
    for channel in (configured_channel, "msedge", "chrome"):
        if channel and channel not in channels:
            channels.append(channel)

    errors: list[str] = []
    for channel in channels:
        kwargs = dict(launch_kwargs)
        kwargs["channel"] = channel
        try:
            return playwright.chromium.launch(**kwargs)
        except Exception as exc:
            errors.append(f"{channel}: {exc}")

    detail = "\n".join(errors)
    raise RuntimeError(
        "浏览器启动失败。当前版本不会下载或使用 Playwright 内置 Chromium。"
        "请确认电脑已安装 Microsoft Edge 或 Google Chrome。"
        + (f"\n{detail}" if detail else "")
    )


def maximize_page_window(page: Page) -> None:
    try:
        session = page.context.new_cdp_session(page)
        window_info = session.send("Browser.getWindowForTarget")
        window_id = window_info.get("windowId")
        if window_id is not None:
            session.send("Browser.setWindowBounds", {"windowId": window_id, "bounds": {"windowState": "maximized"}})
    except Exception:

        pass


def _current_debug_category(page: Page, category: str | None) -> str:
    if category:
        return category
    session = BrowserSession.for_page(page)
    return session.debug_capture.category if session else "chapter_sync"


def _default_debug_enabled(category: str) -> bool:
    env_key = "AUTO_PUBLISH_DEBUG" if category == "auto_publish" else "CHAPTER_SYNC_DEBUG"
    env_value = os.getenv(env_key)
    if env_value is not None:
        return env_value == "1"
    if category == "auto_publish":
        try:
            from backend.infrastructure.persistence.config import load_config

            section = load_config().get("auto_publish", {})
            if isinstance(section, dict):
                return bool(section.get("debugScreenshots", True))
        except Exception:
            return True

    return False


def _debug_dir(category: str):
    return PUBLISH_DEBUG_DIR if category == "auto_publish" else CHAPTER_SYNC_DEBUG_DIR


def _safe_debug_name(name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", str(name or "page"))
    return cleaned.strip("_")[:80] or "page"


def _debug_dedupe_enabled(category: str) -> bool:
    if category == "auto_publish":
        try:
            from backend.infrastructure.persistence.config import load_config

            section = load_config().get("auto_publish", {})
            if isinstance(section, dict):
                return bool(section.get("dedupeDebugScreenshots", True))
        except Exception:
            return True
    return True


def _page_state_fingerprint(page: Page) -> str | None:
    try:
        state = page.evaluate(
            """() => {
                const body = document.body ? document.body.innerText : '';
                const size = `${window.innerWidth}x${window.innerHeight}:${document.documentElement.scrollWidth}x${document.documentElement.scrollHeight}`;
                return `${location.href}\n${document.title}\n${size}\n${body}`;
            }"""
        )
        if isinstance(state, str) and state.strip():
            normalized = "\n".join(line.strip() for line in state.splitlines() if line.strip())
            return hashlib.sha256(normalized.encode("utf-8", errors="ignore")).hexdigest()
    except Exception:
        pass
    return None


def save_debug(page: Page, name: str, *, category: str | None = None, force: bool = False) -> None:
    current_category = _current_debug_category(page, category)
    session = BrowserSession.for_page(page)
    capture = session.debug_capture if session else _fallback_debug_capture(current_category)
    capture.save(page, name, force=force)


def save_failure_debug(page: Page, name: str, *, category: str | None = None) -> None:
    current_category = _current_debug_category(page, category)
    session = BrowserSession.for_page(page)
    capture = session.debug_capture if session else _fallback_debug_capture(current_category)
    capture.save_failure(page, name)


def page_failure_context(
    page: Page,
    stage: str,
    *,
    locator: str = "",
    error: BaseException | None = None,
) -> str:
    try:
        url = str(getattr(page, "url", "") or "<unknown>")
    except Exception:
        url = "<unavailable>"
    details = [f"阶段={stage}", f"URL={url}"]
    if locator:
        details.append(f"定位器={locator}")
    if error is not None:
        details.append(f"异常={type(error).__name__}: {error}")
    return "；".join(details)


_FALLBACK_DEBUG_CAPTURES: dict[str, DebugCapture] = {}


def _fallback_debug_capture(category: str) -> DebugCapture:
    capture = _FALLBACK_DEBUG_CAPTURES.get(category)
    if capture is None:
        capture = DebugCapture(
            category=category,
            enabled=_default_debug_enabled(category),
            failure_enabled=True,
            dedupe_enabled=_debug_dedupe_enabled(category),
        )
        _FALLBACK_DEBUG_CAPTURES[category] = capture
    return capture


def _write_debug_image(page: Page, name: str, *, capture: DebugCapture, force: bool = False) -> None:
    directory = _debug_dir(capture.category)

    fingerprint: str | None = None
    if not force and capture.dedupe_enabled:
        fingerprint = _page_state_fingerprint(page)
        if fingerprint is not None and fingerprint in capture.fingerprints:
            return

    try:
        screenshot_bytes = page.screenshot(full_page=True)
    except Exception:
        return

    if not force and capture.dedupe_enabled:
        if fingerprint is None:
            fingerprint = hashlib.sha256(screenshot_bytes).hexdigest()
        if fingerprint in capture.fingerprints:
            return
        capture.fingerprints.add(fingerprint)

    ts = time.strftime("%Y%m%d_%H%M%S")
    ms = int((time.time() % 1) * 1000)
    seq = next(_DEBUG_COUNTER)
    stem = f"{ts}_{ms:03d}_{seq:04d}_{_safe_debug_name(name)}"
    png_path = directory / f"{stem}.png"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(screenshot_bytes)
    except Exception:
        pass
_DEFAULT_ACCOUNT_ID = "default"
_DEFAULT_ACCOUNT_NAME = "默认账号"


def list_accounts() -> dict[str, Any]:
    data = _load_accounts()
    accounts = _normalize_accounts(data.get("accounts"))
    active_id = str(data.get("active_id") or _DEFAULT_ACCOUNT_ID)
    if active_id not in {item["id"] for item in accounts}:
        active_id = accounts[0]["id"] if accounts else _DEFAULT_ACCOUNT_ID
    return {"ok": True, "activeId": active_id, "accounts": [_public_account(item, active_id=active_id) for item in accounts]}


def add_account(name: str) -> dict[str, Any]:
    display_name = str(name or "").strip() or f"账号{time.strftime('%m%d%H%M')}"
    data = _load_accounts()
    accounts = _normalize_accounts(data.get("accounts"))
    if display_name in {item["name"] for item in accounts}:
        return {"ok": False, "message": "账号名称已存在。", **list_accounts()}
    account_id = _new_account_id(display_name, accounts)
    accounts.append({"id": account_id, "name": display_name, "state_file": str(_state_file_for(account_id))})
    data["accounts"] = accounts
    data["active_id"] = account_id
    _save_accounts(data)
    return {"ok": True, "message": f"已添加并切换到账号：{display_name}", **list_accounts()}


def switch_account(account_id: str) -> dict[str, Any]:
    data = _load_accounts()
    accounts = _normalize_accounts(data.get("accounts"))
    target = next((item for item in accounts if item["id"] == account_id), None)
    if target is None:
        return {"ok": False, "message": "账号不存在。", **list_accounts()}
    data["accounts"] = accounts
    data["active_id"] = account_id
    _save_accounts(data)
    return {"ok": True, "message": f"已切换到账号：{target['name']}", **list_accounts()}


def delete_account(account_id: str) -> dict[str, Any]:
    if account_id == _DEFAULT_ACCOUNT_ID:
        return {"ok": False, "message": "默认账号不能删除。", **list_accounts()}
    data = _load_accounts()
    accounts = _normalize_accounts(data.get("accounts"))
    target = next((item for item in accounts if item["id"] == account_id), None)
    if target is None:
        return {"ok": False, "message": "账号不存在。", **list_accounts()}
    accounts = [item for item in accounts if item["id"] != account_id]
    try:
        _state_file_for(account_id).unlink(missing_ok=True)
    except Exception:
        pass
    active_id = str(data.get("active_id") or _DEFAULT_ACCOUNT_ID)
    if active_id == account_id:
        active_id = accounts[0]["id"] if accounts else _DEFAULT_ACCOUNT_ID
    data["accounts"] = accounts
    data["active_id"] = active_id
    _save_accounts(data)
    return {"ok": True, "message": f"已删除账号：{target['name']}", **list_accounts()}


def resolve_auth_state_file(path: str | Path | None = None) -> Path:
    raw = str(path or "").strip()
    if not raw:
        return FANQIE_AUTH_STATE_FILE
    target = Path(raw).expanduser()
    if target.exists() and target.is_dir():
        return target / "state.json"
    if not target.suffix:
        return target / "state.json"
    return target


def active_auth_state_file() -> Path:
    return FANQIE_AUTH_STATE_FILE


def _load_accounts() -> dict[str, Any]:
    backup_path = FANQIE_ACCOUNTS_FILE.with_name(f"{FANQIE_ACCOUNTS_FILE.name}.bak")
    for candidate in (FANQIE_ACCOUNTS_FILE, backup_path):
        if not candidate.exists():
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                if candidate == backup_path:
                    atomic_write_text(
                        FANQIE_ACCOUNTS_FILE,
                        json.dumps(data, ensure_ascii=False, indent=2),
                    )
                return data
        except (OSError, json.JSONDecodeError):
            LOGGER.warning("无法读取番茄账号索引：%s", candidate, exc_info=True)
    return {"active_id": _DEFAULT_ACCOUNT_ID, "accounts": [_default_account()]}


def _save_accounts(data: dict[str, Any]) -> None:
    BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    FANQIE_ACCOUNT_STATES_DIR.mkdir(parents=True, exist_ok=True)
    accounts = _normalize_accounts(data.get("accounts"))
    active_id = str(data.get("active_id") or _DEFAULT_ACCOUNT_ID)
    if active_id not in {item["id"] for item in accounts}:
        active_id = accounts[0]["id"] if accounts else _DEFAULT_ACCOUNT_ID
    atomic_write_text(
        FANQIE_ACCOUNTS_FILE,
        json.dumps({"active_id": active_id, "accounts": accounts}, ensure_ascii=False, indent=2),
        backup_path=FANQIE_ACCOUNTS_FILE.with_name(f"{FANQIE_ACCOUNTS_FILE.name}.bak"),
    )


def _normalize_accounts(raw: Any) -> list[dict[str, str]]:
    accounts: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        account_id = str(item.get("id") or "").strip()
        name = str(item.get("name") or "").strip()
        if not account_id or not name or account_id in seen:
            continue
        state_file = str(item.get("state_file") or (_state_file_for(account_id) if account_id != _DEFAULT_ACCOUNT_ID else FANQIE_AUTH_STATE_FILE))
        accounts.append({"id": account_id, "name": name, "state_file": state_file})
        seen.add(account_id)
    if _DEFAULT_ACCOUNT_ID not in seen:
        accounts.insert(0, _default_account())
    return accounts


def _default_account() -> dict[str, str]:
    return {"id": _DEFAULT_ACCOUNT_ID, "name": _DEFAULT_ACCOUNT_NAME, "state_file": str(FANQIE_AUTH_STATE_FILE)}


def _public_account(item: dict[str, str], *, active_id: str) -> dict[str, Any]:
    state_file = Path(item.get("state_file") or "")
    return {"id": item["id"], "name": item["name"], "active": item["id"] == active_id, "loggedIn": state_file.exists(), "stateFile": str(state_file)}


def _state_file_for(account_id: str) -> Path:
    if account_id == _DEFAULT_ACCOUNT_ID:
        return FANQIE_AUTH_STATE_FILE
    FANQIE_ACCOUNT_STATES_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^0-9A-Za-z_\-]+", "_", account_id).strip("_") or str(int(time.time()))
    return FANQIE_ACCOUNT_STATES_DIR / f"{safe}.json"


def _new_account_id(name: str, accounts: list[dict[str, str]]) -> str:
    base = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_\-]+", "_", name).strip("_") or "account"
    existing = {item["id"] for item in accounts}
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


__all__ = [
    "BrowserSession",
    "DebugCapture",
    "active_auth_state_file",
    "add_account",
    "delete_account",
    "list_accounts",
    "page_failure_context",
    "resolve_auth_state_file",
    "save_debug",
    "save_failure_debug",
    "switch_account",
]
