from __future__ import annotations

from typing import Callable
from playwright.sync_api import Page

from backend.platforms.fanqie.actions.interactions import locator_count_safe
from backend.platforms.fanqie.browser.session import save_debug

def click_discard_stale_edit_if_present(
    page: Page,
    log: Callable[[str], None] = print,
    timeout_ms: int = 3000,
) -> bool:
    rounds = max(1, timeout_ms // 500)
    for _ in range(rounds):
        try:
            body = page.locator("body").inner_text(timeout=800)
        except Exception:
            body = ""
        if ("刚刚更新的章节" in body and "继续编辑" in body) or ("是否继续编辑" in body and "继续编辑" in body):
            log("检测到章节已在其他会话更新，自动放弃旧编辑缓存并加载最新版本...")
            save_debug(page, "dialog_discard_stale_edit_detected")
            try:
                loc = page.get_by_role("button", name="放弃", exact=True)
                count = locator_count_safe(loc)
                for i in reversed(range(count)):
                    item = loc.nth(i)
                    try:
                        if item.is_visible() and item.is_enabled():
                            item.scroll_into_view_if_needed()
                            item.click(timeout=5000)
                            save_debug(page, "dialog_discard_stale_edit_clicked")
                            page.wait_for_timeout(1800)
                            return True
                    except Exception:
                        continue
            except Exception:
                pass
            script = r"""
            () => {
                function visible(el) {
                    if (!el) return false;
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0 &&
                           style.visibility !== 'hidden' &&
                           style.display !== 'none' &&
                           rect.bottom >= 0 &&
                           rect.right >= 0 &&
                           rect.top <= window.innerHeight &&
                           rect.left <= window.innerWidth;
                }
                function compactText(el) {
                    return ((el && (el.innerText || el.textContent)) || '').replace(/\s+/g, '').trim();
                }
                const roots = Array.from(document.querySelectorAll(
                    '[role="dialog"], .arco-modal-content, .arco-modal, .byte-modal, .byte-modal-content, .semi-modal-content, .semi-modal, div'
                ))
                    .filter(visible)
                    .map(el => {
                        const rect = el.getBoundingClientRect();
                        const text = compactText(el);
                        const area = rect.width * rect.height;
                        let score = 0;
                        if (text.includes('刚刚更新的章节')) score += 10;
                        if (text.includes('是否继续编辑')) score += 10;
                        if (text.includes('继续编辑')) score += 10;
                        if (text.includes('放弃')) score += 10;
                        if (rect.width >= 300 && rect.width <= 760 && rect.height >= 160 && rect.height <= 520) score += 4;
                        return {el, rect, text, area, score};
                    })
                    .filter(x => x.score >= 12)
                    .sort((a, b) => b.score - a.score || a.area - b.area);
                const root = roots.length ? roots[0].el : document.body;
                const buttons = Array.from(root.querySelectorAll('button, span, div'))
                    .filter(visible)
                    .filter(el => compactText(el) === '放弃');
                for (const el of buttons.reverse()) {
                    const clickable = el.closest('button') || el;
                    try {
                        clickable.click();
                        return true;
                    } catch (e) {
                        try {
                            el.click();
                            return true;
                        } catch (e2) {}
                    }
                }
                return false;
            }
            """
            try:
                if page.evaluate(script):
                    save_debug(page, "dialog_discard_stale_edit_clicked_js")
                    page.wait_for_timeout(1800)
                    return True
            except Exception:
                pass
            raise RuntimeError("检测到章节更新提示，但未能点击“放弃”以清除旧编辑缓存。")
        page.wait_for_timeout(500)
    return False

def click_typo_submit_if_present(page: Page, log: Callable[[str], None] = print, timeout_ms: int = 3000) -> bool:
    return _click_submit_prompt_if_present(
        page,
        marker_groups=[
            ["发布提示", "错别字", "提交"],
            ["错别字未修改", "提交"],
        ],
        log_message="检测到错别字发布提示，自动点击提交...",
        debug_name="dialog_typo_submit",
        error_message="检测到错别字发布提示，但未能点击“提交”。",
        log=log,
        timeout_ms=timeout_ms,
    )


def click_non_chapter_submit_if_present(
    page: Page,
    log: Callable[[str], None] = print,
    timeout_ms: int = 3000,
) -> bool:
    return _click_submit_prompt_if_present(
        page,
        marker_groups=[["非章节内容", "作者有话说", "提交"]],
        log_message="检测到非章节内容提示，自动点击提交...",
        debug_name="dialog_non_chapter_submit",
        error_message="检测到非章节内容提示，但未能点击“提交”。",
        log=log,
        timeout_ms=timeout_ms,
    )


def _click_submit_prompt_if_present(
    page: Page,
    *,
    marker_groups: list[list[str]],
    log_message: str,
    debug_name: str,
    error_message: str,
    log: Callable[[str], None],
    timeout_ms: int,
) -> bool:
    rounds = max(1, timeout_ms // 500)
    for _ in range(rounds):
        try:
            body = page.locator("body").inner_text(timeout=800)
        except Exception:
            body = ""
        if any(all(marker in body for marker in markers) for markers in marker_groups):
            log(log_message)
            save_debug(page, f"{debug_name}_detected")

            try:
                loc = page.get_by_text("提交", exact=True)
                count = locator_count_safe(loc)
                for i in reversed(range(count)):
                    item = loc.nth(i)
                    try:
                        if item.is_visible() and item.is_enabled():
                            item.scroll_into_view_if_needed()
                            item.click(timeout=5000)
                            save_debug(page, f"{debug_name}_clicked")
                            page.wait_for_timeout(1200)
                            return True
                    except Exception:
                        continue
            except Exception:
                pass

            script = r"""
            (criteria) => {
                function visible(el) {
                    if (!el) return false;
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return rect.width > 0 && rect.height > 0 &&
                           style.visibility !== 'hidden' &&
                           style.display !== 'none' &&
                           rect.bottom >= 0 &&
                           rect.right >= 0 &&
                           rect.top <= window.innerHeight &&
                           rect.left <= window.innerWidth;
                }
                function compactText(el) {
                    return ((el && (el.innerText || el.textContent)) || '').replace(/\s+/g, '').trim();
                }
                const roots = Array.from(document.querySelectorAll(
                    '[role="dialog"], .arco-modal-content, .arco-modal, .byte-modal, .byte-modal-content, .semi-modal-content, .semi-modal, div'
                ))
                    .filter(visible)
                    .map(el => {
                        const rect = el.getBoundingClientRect();
                        const text = compactText(el);
                        const area = rect.width * rect.height;
                        let score = 0;
                        const matched = criteria.markerGroups.some(
                            markers => markers.every(marker => text.includes(marker))
                        );
                        if (matched) score += 30;
                        if (text.includes('提交')) score += 8;
                        if (rect.width >= 300 && rect.width <= 760 && rect.height >= 180 && rect.height <= 600) score += 3;
                        return {el, rect, text, area, score};
                    })
                    .filter(x => x.score >= 30)
                    .sort((a, b) => b.score - a.score || a.area - b.area);
                const root = roots.length ? roots[0].el : document.body;
                const buttons = Array.from(root.querySelectorAll('button, span, div'))
                    .filter(visible)
                    .filter(el => compactText(el) === '提交');
                for (const el of buttons.reverse()) {
                    const clickable = el.closest('button') || el;
                    try {
                        clickable.click();
                        return true;
                    } catch (e) {
                        try {
                            el.click();
                            return true;
                        } catch (e2) {}
                    }
                }
                if (roots.length) {
                    const rect = roots[0].rect;
                    const points = [
                        [rect.left + rect.width * 0.78, rect.top + rect.height * 0.82],
                        [rect.left + rect.width * 0.82, rect.top + rect.height * 0.82],
                        [rect.left + rect.width * 0.75, rect.top + rect.height * 0.80],
                    ];
                    for (const [x, y] of points) {
                        const target = document.elementFromPoint(x, y);
                        if (!target) continue;
                        const clickable = target.closest('button') || target;
                        try {
                            clickable.click();
                            return true;
                        } catch (e) {}
                    }
                }
                return false;
            }
            """
            try:
                if page.evaluate(script, {"markerGroups": marker_groups}):
                    save_debug(page, f"{debug_name}_clicked_js")
                    page.wait_for_timeout(1200)
                    return True
            except Exception:
                pass
            raise RuntimeError(error_message)
        page.wait_for_timeout(500)
    return False
