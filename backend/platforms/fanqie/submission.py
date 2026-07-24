from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from backend.platforms.fanqie.actions.interactions import locator_count_safe
from backend.platforms.fanqie.browser.session import page_failure_context, save_debug, save_failure_debug
from backend.platforms.fanqie.dialogs.editing import (
    click_continue_edit_if_present,
    click_non_chapter_submit_if_present,
    click_typo_submit_if_present,
)
from backend.platforms.fanqie.dialogs.publishing import (
    choose_ai_option,
    click_basic_content_check_if_present,
    click_confirm_publish,
    daily_submit_limit_visible,
    ensure_scheduled_publish,
    ensure_scheduled_publish_at_10,
    publish_settings_visible,
)
from backend.platforms.fanqie.models import ScheduledPublishSlot


class SubmissionMode(str, Enum):
    PUBLISH = "publish"
    SYNC = "sync"


class SubmissionPhase(str, Enum):
    READY = "ready"
    ENTERING_SETTINGS = "entering_settings"
    CONFIGURING = "configuring"
    CONFIRMING = "confirming"
    COMPLETED = "completed"


@dataclass(slots=True)
class SubmissionFlow:
    page: Page
    mode: SubmissionMode
    use_ai: bool = False
    log: Callable[[str], None] = print
    scheduled_slot: ScheduledPublishSlot | None = None
    phase: SubmissionPhase = SubmissionPhase.READY
    daily_limit_reschedule_attempts: int = 0
    _reported_failures: set[str] = field(default_factory=set, init=False)

    @property
    def debug_prefix(self) -> str:
        return self.mode.value

    @property
    def settings_label(self) -> str:
        return "发布设置" if self.mode is SubmissionMode.PUBLISH else "提交设置"

    def run(self) -> None:
        save_debug(self.page, f"{self.debug_prefix}_flow_start")
        self.enter_settings()
        confirmed = False

        for round_no in range(1, 70):
            handled = self._handle_intermediate_dialogs(timeout_ms=300)

            if publish_settings_visible(self.page):
                self.phase = SubmissionPhase.CONFIGURING
                save_debug(self.page, f"{self.debug_prefix}_settings_visible_round_{round_no}")
                self._configure_publish_settings()
                self.phase = SubmissionPhase.CONFIRMING
                click_confirm_publish(self.page, log=self.log)
                confirmed = True
                handled = True

            if confirmed:
                handled = self._handle_post_confirmation_dialogs() or handled
                if not self._has_blocking_dialog():
                    self.phase = SubmissionPhase.COMPLETED
                    save_debug(self.page, f"{self.debug_prefix}_flow_done")
                    self.log(
                        "发布确认流程完成。"
                        if self.mode is SubmissionMode.PUBLISH
                        else "同步提交确认流程完成。"
                    )
                    return

            if not handled:
                self.page.wait_for_timeout(600)

        save_debug(self.page, f"{self.debug_prefix}_flow_timeout", force=True)
        action = "发布确认" if self.mode is SubmissionMode.PUBLISH else "同步提交确认"
        raise RuntimeError(
            f"{action}流程超时：可能停在内容检测方式、错别字提示、非章节内容提示、AI 设置或确认发布弹窗。"
        )

    def enter_settings(self) -> None:
        self.phase = SubmissionPhase.ENTERING_SETTINGS
        self.log("正在点击下一步...")
        save_debug(self.page, f"{self.debug_prefix}_next_step_before")

        for attempt in range(1, 4):
            if not self._click_next_step_once():
                if attempt == 3:
                    self._report_failure_once(
                        "next_step_not_found",
                        stage="进入提交设置",
                        locator='role=button[name="下一步"] / DOM fallback',
                    )
                    raise RuntimeError(
                        "未找到“下一步”按钮。"
                        + page_failure_context(
                            self.page,
                            "进入提交设置",
                            locator='role=button[name="下一步"] / DOM fallback',
                        )
                    )
                self.page.wait_for_timeout(1000)
                continue

            for _ in range(80):
                if self._wait_for_settings_or_handle_dialog():
                    self.phase = SubmissionPhase.CONFIGURING
                    return

            if attempt < 3:
                save_debug(self.page, f"{self.debug_prefix}_settings_not_visible_attempt_{attempt}")
                self.log(f"未等到{self.settings_label}弹窗，重试点击“下一步”...")
                self.page.wait_for_timeout(1200)

        save_debug(self.page, f"{self.debug_prefix}_next_step_failed", force=True)
        raise RuntimeError(f"点击“下一步”后仍未检测到{self.settings_label}弹窗，可能被页面校验/保存状态拦截。")

    def _click_next_step_once(self) -> bool:
        last_error: PlaywrightError | None = None
        try:
            buttons = self.page.get_by_role("button", name="下一步", exact=True)
            for index in reversed(range(locator_count_safe(buttons))):
                button = buttons.nth(index)
                try:
                    button.click(timeout=10000)
                    return True
                except PlaywrightError as exc:
                    last_error = exc
                    continue
        except PlaywrightError as exc:
            last_error = exc
        clicked = self._click_next_step_with_dom_fallback()
        if not clicked and last_error is not None:
            self._report_failure_once(
                "next_step_role_failed",
                stage="点击下一步",
                locator='role=button[name="下一步"]',
                error=last_error,
            )
        return clicked

    def _click_next_step_with_dom_fallback(self) -> bool:
        script = r"""
        () => {
            function visible(el) {
                if (!el) return false;
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return rect.width > 0 && rect.height > 0 &&
                       style.visibility !== 'hidden' && style.display !== 'none';
            }
            function disabled(el) {
                const cls = String(el.className || '').toLowerCase();
                return el.disabled === true ||
                       el.getAttribute('aria-disabled') === 'true' ||
                       el.getAttribute('disabled') !== null ||
                       cls.includes('disabled') || cls.includes('disable');
            }
            function compactText(el) {
                return ((el && (el.innerText || el.textContent)) || '').replace(/\s+/g, '').trim();
            }
            const candidates = Array.from(document.querySelectorAll('button, [role="button"], a'))
                .filter(visible)
                .filter(el => compactText(el) === '下一步')
                .filter(el => !disabled(el));
            for (const candidate of candidates.reverse()) {
                try {
                    candidate.click();
                    return true;
                } catch (error) {}
            }
            return false;
        }
        """
        try:
            return bool(self.page.evaluate(script))
        except PlaywrightError as exc:
            self._report_failure_once(
                "next_step_dom_failed",
                stage="点击下一步 DOM 回退",
                locator='button, [role="button"], a',
                error=exc,
            )
            return False

    def _wait_for_settings_or_handle_dialog(self) -> bool:
        if click_basic_content_check_if_present(self.page, log=self.log, timeout_ms=500):
            self.page.wait_for_timeout(1000)
        if publish_settings_visible(self.page):
            save_debug(self.page, f"{self.debug_prefix}_settings_visible_after_next")
            return True
        if click_continue_edit_if_present(self.page, log=self.log, timeout_ms=500):
            self.page.wait_for_timeout(800)
        if click_typo_submit_if_present(self.page, log=self.log, timeout_ms=500):
            self.page.wait_for_timeout(1000)
        if click_non_chapter_submit_if_present(self.page, log=self.log, timeout_ms=500):
            self.page.wait_for_timeout(1000)
        if publish_settings_visible(self.page):
            save_debug(self.page, f"{self.debug_prefix}_settings_visible_after_dialog")
            return True
        self.page.wait_for_timeout(500)
        return False

    def _handle_intermediate_dialogs(self, *, timeout_ms: int) -> bool:
        handlers = (
            click_basic_content_check_if_present,
            click_continue_edit_if_present,
            click_typo_submit_if_present,
            click_non_chapter_submit_if_present,
        )
        handled = False
        for handler in handlers:
            if handler(self.page, log=self.log, timeout_ms=timeout_ms):
                handled = True
        return handled

    def _configure_publish_settings(self) -> None:
        if self.scheduled_slot is not None:
            ensure_scheduled_publish(
                self.page,
                scheduled_date=self.scheduled_slot.date,
                scheduled_time=self.scheduled_slot.time,
                log=self.log,
            )
        elif daily_submit_limit_visible(self.page):
            if self.daily_limit_reschedule_attempts >= 31:
                raise RuntimeError("检测到每日提交字数上限，已连续尝试向后顺延 31 次定时发布日期，仍未通过。")
            ensure_scheduled_publish_at_10(
                self.page,
                date_increment_days=self.daily_limit_reschedule_attempts + 1,
                log=self.log,
            )
            self.daily_limit_reschedule_attempts += 1
        choose_ai_option(self.page, use_ai=self.use_ai, log=self.log)

    def _handle_post_confirmation_dialogs(self) -> bool:
        handled_typo = click_typo_submit_if_present(self.page, log=self.log, timeout_ms=300)
        handled_non_chapter = click_non_chapter_submit_if_present(self.page, log=self.log, timeout_ms=300)
        return handled_typo or handled_non_chapter

    def _has_blocking_dialog(self) -> bool:
        try:
            body = self.page.locator("body").inner_text(timeout=800)
        except PlaywrightError as exc:
            self._report_failure_once(
                "blocking_dialog_read_failed",
                stage="确认提交结果",
                locator="body",
                error=exc,
            )
            return True
        compact = "".join(body.split())
        return (
            ("发布设置" in compact)
            or ("是否使用AI" in compact)
            or ("确认发布" in compact)
            or ("请选择内容检测方式" in compact)
            or ("仅基础检测" in compact and "全面检测" in compact)
            or ("错别字" in compact and "提交" in compact)
            or ("非章节内容" in compact and "作者有话说" in compact and "提交" in compact)
            or ("继续编辑" in compact and "刚刚更新" in compact)
        )

    def _report_failure_once(
        self,
        key: str,
        *,
        stage: str,
        locator: str = "",
        error: BaseException | None = None,
    ) -> None:
        if key in self._reported_failures:
            return
        self._reported_failures.add(key)
        save_failure_debug(self.page, f"{self.debug_prefix}_{key}")
        self.log(f"页面操作失败：{page_failure_context(self.page, stage, locator=locator, error=error)}")


__all__ = ["SubmissionFlow", "SubmissionMode", "SubmissionPhase"]
