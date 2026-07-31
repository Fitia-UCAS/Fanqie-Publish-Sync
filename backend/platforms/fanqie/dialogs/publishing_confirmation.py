
from __future__ import annotations

from playwright.sync_api import Page

from backend.platforms.fanqie.actions.interactions import locator_count_safe
from backend.platforms.fanqie.browser.session import page_failure_context, save_debug, save_failure_debug

def click_confirm_publish(page: Page, log=print) -> None:
    log("正在确认发布...")
    save_debug(page, "publish_confirm_before_click")

    for _ in range(12):
        for loc in (
            page.get_by_role("button", name="确认发布", exact=True),
            page.get_by_text("确认发布", exact=True),
        ):
            try:
                count = locator_count_safe(loc)
            except Exception:
                continue
            for i in reversed(range(count)):
                item = loc.nth(i)
                try:
                    if not item.is_visible() or not item.is_enabled():
                        continue
                    item.scroll_into_view_if_needed()
                    item.click(timeout=5000)
                    save_debug(page, "publish_confirm_clicked")
                    page.wait_for_timeout(1200)
                    return
                except Exception:
                    continue
        page.wait_for_timeout(500)

    script = r"""
    () => {
        function visible(el) {
            if (!el) return false;
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 &&
                   style.visibility !== 'hidden' && style.display !== 'none' &&
                   !el.disabled && el.getAttribute('aria-disabled') !== 'true';
        }
        function compactText(el) {
            return ((el && (el.innerText || el.textContent)) || '').replace(/\s+/g, '').trim();
        }
        const candidates = Array.from(document.querySelectorAll('button, [role="button"]'))
            .filter(visible)
            .filter(el => compactText(el) === '确认发布')
            .sort((a, b) => {
                const ar = a.getBoundingClientRect();
                const br = b.getBoundingClientRect();
                return br.top - ar.top || br.left - ar.left;
            });
        for (const candidate of candidates) {
            try {
                candidate.scrollIntoView({block: 'center', inline: 'nearest'});
                candidate.click();
                return true;
            } catch (_) {}
        }
        return false;
    }
    """
    if not page.evaluate(script):
        save_failure_debug(page, "publish_confirm_not_found")
        raise RuntimeError(
            "未找到可点击的“确认发布”按钮。"
            + page_failure_context(
                page,
                "确认发布",
                locator='role=button[name="确认发布"] / exact text / DOM button fallback',
            )
        )
    save_debug(page, "publish_confirm_clicked_js")
    page.wait_for_timeout(1200)
