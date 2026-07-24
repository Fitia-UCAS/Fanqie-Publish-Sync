from __future__ import annotations

from typing import Callable

from playwright.sync_api import Page

from backend.platforms.fanqie.browser.session import save_debug
from backend.platforms.fanqie.dialogs.publishing_schedule_date import (
    set_automatic_scheduled_publish_date,
    set_manual_scheduled_publish_date,
)
from backend.platforms.fanqie.dialogs.publishing_schedule_switch import ensure_scheduled_publish_switch_on
from backend.platforms.fanqie.dialogs.publishing_schedule_time import set_scheduled_publish_time

DAILY_SUBMIT_LIMIT_KEYWORDS = (
    "提交字数超出每日上限",
    "提交字数超过每日上限",
    "字数超出每日上限",
    "字数超过每日上限",
    "超过本日提交字数",
    "超出本日提交字数",
    "本日提交的字数",
)
DEFAULT_SCHEDULED_PUBLISH_TIME = "10:00"


def daily_submit_limit_visible(page: Page) -> bool:
    try:
        body = page.locator("body").inner_text(timeout=800)
    except Exception:
        body = ""
    compact = "".join(body.split())
    if any(keyword in compact for keyword in DAILY_SUBMIT_LIMIT_KEYWORDS):
        return True
    return ("每日上限" in compact or "本日" in compact) and ("提交字数" in compact or "投稿字数" in compact)


def ensure_scheduled_publish_at_10(
    page: Page,
    *,
    scheduled_time: str = DEFAULT_SCHEDULED_PUBLISH_TIME,
    date_increment_days: int = 0,
    log: Callable[[str], None] = print,
) -> str:
    save_debug(page, "schedule_publish_before")
    if not ensure_scheduled_publish_switch_on(page):
        save_debug(page, "schedule_publish_toggle_failed", force=True)
        raise RuntimeError("检测到每日提交字数上限，但未能打开“定时发布”开关。")
    page.wait_for_timeout(600)
    save_debug(page, "schedule_publish_toggle_on")

    scheduled_date = set_automatic_scheduled_publish_date(page, date_increment_days=date_increment_days)
    log(f"检测到提交字数超过每日上限，自动改为定时发布，发布日期设为 {scheduled_date}，发布时间设为 {scheduled_time}。")
    save_debug(page, "schedule_publish_date_set")

    if not set_scheduled_publish_time(page, scheduled_time=scheduled_time):
        save_debug(page, "schedule_publish_time_input_not_found", force=True)
        raise RuntimeError("检测到每日提交字数上限，但未能定位“定时发布”的时间输入框。")
    page.wait_for_timeout(400)
    save_debug(page, "schedule_publish_time_set")
    return scheduled_date


def ensure_scheduled_publish(
    page: Page,
    *,
    scheduled_date: str,
    scheduled_time: str,
    log: Callable[[str], None] = print,
) -> str:
    save_debug(page, "schedule_publish_manual_before")
    if not ensure_scheduled_publish_switch_on(page):
        save_debug(page, "schedule_publish_manual_toggle_failed", force=True)
        raise RuntimeError("未能打开“定时发布”开关。")
    if not set_manual_scheduled_publish_date(page, scheduled_date=scheduled_date):
        save_debug(page, "schedule_publish_manual_date_input_not_found", force=True)
        raise RuntimeError("未能定位“定时发布”的日期输入框。")
    if not set_scheduled_publish_time(page, scheduled_time=scheduled_time):
        save_debug(page, "schedule_publish_manual_time_input_not_found", force=True)
        raise RuntimeError("未能定位“定时发布”的时间输入框。")
    save_debug(page, "schedule_publish_manual_set")
    log(f"已设置定时发布：{scheduled_date} {scheduled_time}。")
    return scheduled_date


__all__ = [
    "daily_submit_limit_visible",
    "ensure_scheduled_publish",
    "ensure_scheduled_publish_at_10",
]
