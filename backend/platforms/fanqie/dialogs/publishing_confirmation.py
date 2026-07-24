
from __future__ import annotations

from playwright.sync_api import Page

from backend.platforms.fanqie.actions.interactions import locator_count_safe
from backend.platforms.fanqie.browser.session import save_debug

def click_confirm_publish(page: Page, log=print) -> None:
    log("正在确认发布...")
    save_debug(page, "publish_confirm_before_click")

    for _ in range(12):
        try:
            loc = page.get_by_text("确认发布", exact=True)
            count = locator_count_safe(loc)
            for i in range(count):
                item = loc.nth(i)
                if item.is_visible():
                    try:
                        item.scroll_into_view_if_needed()
                        item.click(timeout=5000)
                        save_debug(page, "publish_confirm_clicked")
                        page.wait_for_timeout(1200)
                        return
                    except Exception:
                        pass
        except Exception:
            pass
        page.wait_for_timeout(500)

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
        function clickAt(x, y) {
            const el = document.elementFromPoint(x, y);
            if (!el) return false;
            const clickable = el.closest('button') || el;
            try {
                clickable.click();
                return true;
            } catch (e) {
                try {
                    el.click();
                    return true;
                } catch (e2) {
                    return false;
                }
            }
        }
        const candidates = Array.from(document.querySelectorAll('[role="dialog"], .arco-modal-content, .arco-modal, .byte-modal, .byte-modal-content, .semi-modal-content, .semi-modal, div'))
            .filter(visible)
            .map(el => {
                const rect = el.getBoundingClientRect();
                const text = compactText(el);
                const area = rect.width * rect.height;
                let score = 0;
                if (text.includes('发布设置')) score += 10;
                if (text.includes('确认发布')) score += 10;
                if (rect.width >= 350 && rect.width <= 760 && rect.height >= 250 && rect.height <= 700) score += 4;
                return {el, rect, text, area, score};
            })
            .filter(x => x.score >= 4)
            .sort((a, b) => b.score - a.score || a.area - b.area);
        const rect = candidates.length ? candidates[0].rect : null;
        if (!rect) return false;
        const points = [
            [rect.left + rect.width * 0.84, rect.top + rect.height * 0.91],
            [rect.left + rect.width * 0.80, rect.top + rect.height * 0.91],
            [rect.left + rect.width * 0.87, rect.top + rect.height * 0.91],
        ];
        for (const [x, y] of points) {
            if (clickAt(x, y)) return true;
        }
        return false;
    }
    """
    if not page.evaluate(script):
        raise RuntimeError("未找到“确认发布”按钮。")
    save_debug(page, "publish_confirm_clicked_js")
    page.wait_for_timeout(1200)

