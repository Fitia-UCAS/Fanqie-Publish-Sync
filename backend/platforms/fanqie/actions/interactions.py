from __future__ import annotations

import time
from typing import Callable, Optional

from playwright.sync_api import Locator, Page

from backend.features.novel_processing.text_normalizer import chinese_to_int
from backend.platforms.fanqie.browser.session import save_debug

def locator_count_safe(locator: Locator) -> int:
    try:
        return locator.count()
    except Exception:
        return 0

def first_visible(locator: Locator) -> Optional[Locator]:
    count = locator_count_safe(locator)
    for i in range(count):
        item = locator.nth(i)
        try:
            if item.is_visible():
                return item
        except Exception:
            continue
    return None

def wait_briefly_for_page_ready(page: Page, timeout_ms: int = 4000) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    except Exception:
        pass
    try:
        page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 2500))
    except Exception:

        pass

def goto_chapter_manage(page: Page, chapter_manage_url: str) -> None:
    page.goto(chapter_manage_url, wait_until="domcontentloaded", timeout=60000)
    wait_briefly_for_page_ready(page)

def page_text(page: Page, limit: int = 4000) -> str:
    try:
        text = page.locator("body").inner_text(timeout=5000)
        return text[:limit]
    except Exception:
        return ""

def ensure_logged_in(
    page: Page,
    chapter_manage_url: str,
    log: Callable[[str], None] = print,
    timeout_ms: int = 900000,
    wait_for_login: bool = False,
) -> None:
    if not _is_login_page(page):
        return
    if not wait_for_login:
        raise RuntimeError("尚未登录或登录状态已过期，请先通过账号登录入口完成登录。")
    log("检测到未登录，请在浏览器中完成番茄账号登录。程序会在登录成功后自动继续。")
    deadline = time.monotonic() + max(timeout_ms, 1000) / 1000
    last_notice = 0.0
    while time.monotonic() < deadline:
        if page.is_closed():
            raise RuntimeError("登录浏览器已关闭，登录已取消。")
        if not _is_login_page(page):
            log("登录状态已确认，正在继续任务。")
            goto_chapter_manage(page, chapter_manage_url)
            return
        now = time.monotonic()
        if now - last_notice >= 60:
            log("仍在等待登录，请在浏览器中完成操作。")
            last_notice = now
        page.wait_for_timeout(1000)
    raise RuntimeError("等待登录超时，请重新启动任务后完成登录。")


def _is_login_page(page: Page) -> bool:
    url = str(page.url or "").lower()
    text = page_text(page)
    return "passport" in url or "login" in url or ("登录" in text and "章节" not in text and "作品" not in text)


def dismiss_popups(page: Page) -> None:
    for word in ["我知道了", "知道了", "取消"]:
        try:
            loc = page.get_by_text(word, exact=True)
            count = locator_count_safe(loc)
            for i in range(count):
                item = loc.nth(i)
                if item.is_visible():
                    save_debug(page, f"popup_before_click_{word}")
                    item.click(timeout=1500)
                    save_debug(page, f"popup_after_click_{word}")
                    page.wait_for_timeout(500)
                    return
        except Exception:
            pass

def normalize_chapter_no(raw: str) -> Optional[int]:
    value = chinese_to_int(str(raw or "").strip())
    return value if value and value > 0 else None
