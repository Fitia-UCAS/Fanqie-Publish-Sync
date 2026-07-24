
from __future__ import annotations

from playwright.sync_api import Page

def _ensure_scheduled_publish_switch_on(page: Page) -> bool:
    script = r'''
    () => {
        function visible(el) {
            if (!el) return false;
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 &&
                   style.visibility !== 'hidden' &&
                   style.display !== 'none' &&
                   rect.bottom >= 0 && rect.right >= 0 &&
                   rect.top <= window.innerHeight && rect.left <= window.innerWidth;
        }
        function compactText(el) {
            return ((el && (el.innerText || el.textContent)) || '').replace(/\s+/g, '').trim();
        }
        function fieldsVisible() {
            const compact = compactText(document.body);
            return compact.includes('定时发布') && compact.includes('日期') &&
                   compact.includes('时间') && compact.includes('预告关键词');
        }
        function isOn(el) {
            if (!el) return false;
            const cls = String(el.className || '').toLowerCase();
            const aria = String(el.getAttribute('aria-checked') || '').toLowerCase();
            return el.checked === true || aria === 'true' ||
                cls.includes('checked') || cls.includes('on') || cls.includes('open') || cls.includes('active');
        }
        function clickElement(el) {
            if (!el || !visible(el)) return false;
            try {
                el.scrollIntoView({block: 'center', inline: 'center'});
                el.click();
                return true;
            } catch (e) {
                return false;
            }
        }
        if (fieldsVisible()) return true;
        const labelNodes = [];
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        for (let node; (node = walker.nextNode());) {
            if (!node.nodeValue || !node.nodeValue.includes('定时发布')) continue;
            const parent = node.parentElement;
            if (parent && visible(parent)) labelNodes.push(parent);
        }
        const switchSelectors = [
            '[role="switch"]',
            'button[aria-checked]',
            'input[type="checkbox"]',
            '.arco-switch',
            '.semi-switch',
            '.byte-switch',
            '[class*="switch"]',
            '[class*="Switch"]'
        ];
        const candidates = [];
        for (const label of labelNodes) {
            let root = label;
            for (let depth = 0; depth < 6 && root; depth++, root = root.parentElement) {
                for (const selector of switchSelectors) {
                    for (const sw of Array.from(root.querySelectorAll(selector))) {
                        if (!visible(sw)) continue;
                        const rect = sw.getBoundingClientRect();
                        const distance = Math.abs((rect.top + rect.height / 2) - (label.getBoundingClientRect().top + label.getBoundingClientRect().height / 2));
                        candidates.push({el: sw, rect, distance});
                    }
                }
            }
        }
        candidates.sort((a, b) => a.distance - b.distance || b.rect.left - a.rect.left);
        for (const item of candidates) {
            if (isOn(item.el)) return true;
            const clickable = item.el.closest('button, [role="switch"], label, [role="button"]') || item.el;
            if (clickElement(clickable) || clickElement(item.el)) return true;
        }
        for (const label of labelNodes) {
            const rect = label.getBoundingClientRect();
            const points = [
                [rect.right + 44, rect.top + rect.height / 2],
                [rect.right + 70, rect.top + rect.height / 2],
                [rect.right + 95, rect.top + rect.height / 2],
            ];
            for (const [x, y] of points) {
                const target = document.elementFromPoint(x, y);
                const clickable = target && (target.closest('button, [role="switch"], [role="button"], label') || target);
                if (clickElement(clickable)) return true;
            }
        }
        return fieldsVisible();
    }
    '''
    try:
        if page.evaluate(script):
            return True
    except Exception:
        pass
    for _ in range(10):
        try:
            body = page.locator("body").inner_text(timeout=500)
        except Exception:
            body = ""
        compact = "".join(body.split())
        if "定时发布" in compact and "日期" in compact and "时间" in compact and "预告关键词" in compact:
            return True
        page.wait_for_timeout(300)
    return False


def ensure_scheduled_publish_switch_on(page: Page) -> bool:
    return _ensure_scheduled_publish_switch_on(page)


__all__ = ["ensure_scheduled_publish_switch_on"]


