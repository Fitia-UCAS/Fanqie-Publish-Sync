
from __future__ import annotations

from playwright.sync_api import Locator, Page

from backend.features.novel_processing.text_normalizer import normalize_novel_body
from backend.platforms.fanqie.browser.session import save_debug
from backend.platforms.fanqie.pages.editor_fields import EditorWriteNotReady
from backend.runtime.errors import TaskCancelled
from backend.runtime.jobs.cancellation import CancellationGuard

def _wait_for_editable_ready(
    page: Page,
    loc: Locator,
    *,
    timeout_ms: int = 4000,
    cancel: CancellationGuard | None = None,
) -> bool:
    cancel = cancel or CancellationGuard()
    cancel.checkpoint()
    try:
        loc.wait_for(state="visible", timeout=timeout_ms)
    except Exception:
        return False
    try:
        ready = loc.evaluate(
            """(el, timeoutMs) => new Promise(resolve => {
                const started = Date.now();
                const ready = () => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    const editable = el.isContentEditable ||
                        el.getAttribute('contenteditable') === 'true' ||
                        String(el.className || '').toLowerCase().includes('prosemirror') ||
                        String(el.className || '').toLowerCase().includes('ql-editor') ||
                        String(el.className || '').toLowerCase().includes('drafteditor') ||
                        String(el.className || '').toLowerCase().includes('public-drafteditor') ||
                        el.getAttribute('role') === 'textbox';
                    return editable && rect.width > 0 && rect.height > 0 &&
                        style.visibility !== 'hidden' && style.display !== 'none' &&
                        !el.hasAttribute('disabled') && el.getAttribute('aria-disabled') !== 'true';
                };
                const tick = () => {
                    if (ready()) {
                        resolve(true);
                        return;
                    }
                    if (Date.now() - started > timeoutMs) {
                        resolve(false);
                        return;
                    }
                    requestAnimationFrame(tick);
                };
                tick();
            })""",
            max(250, timeout_ms - 250),
        )
    except Exception:
        return False
    if not ready:
        return False
    try:
        loc.evaluate("el => { el.scrollIntoView({block: 'center', inline: 'nearest'}); el.focus(); }")
    except Exception:
        return False
    cancel.wait_page(page, 300)
    return True


def _locator_text(loc: Locator) -> str:
    try:
        tag = str(loc.evaluate("el => (el.tagName || '').toLowerCase()"))
    except Exception:
        tag = ""
    if tag in {"input", "textarea"}:
        try:
            return str(loc.input_value(timeout=1000) or "")
        except Exception:
            return ""
    try:
        value = loc.evaluate("el => el.innerText || el.textContent || ''")
        return str(value or "")
    except Exception:
        return ""


def _text_was_written(loc: Locator, text: str) -> bool:
    expected = normalize_novel_body(text)
    current = normalize_novel_body(_locator_text(loc))
    return current == expected


def _fill_editable_by_paste(
    page: Page,
    loc: Locator,
    text: str,
    *,
    cancel: CancellationGuard | None = None,
) -> bool:
    cancel = cancel or CancellationGuard()
    cancel.checkpoint()
    save_debug(page, "body_fill_paste_before")
    try:
        loc.evaluate("el => el.scrollIntoView({block: 'center', inline: 'nearest'})")
    except Exception:
        pass
    try:
        loc.click(timeout=5000, force=True)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.evaluate("text => navigator.clipboard && navigator.clipboard.writeText(text)", text)
        page.keyboard.press("Control+V")
        cancel.wait_page(page, 450)

        page.keyboard.press("End")
        page.keyboard.press("Space")
        cancel.wait_page(page, 120)
        page.keyboard.press("Backspace")
        cancel.wait_page(page, 350)
        ok = _text_was_written(loc, text)
        save_debug(page, "body_fill_paste_success" if ok else "body_fill_paste_failed")
        return ok
    except TaskCancelled:
        raise
    except Exception:
        save_debug(page, "body_fill_paste_exception")
        return False


def _fill_editable_by_dom(
    page: Page,
    loc: Locator,
    text: str,
    *,
    cancel: CancellationGuard | None = None,
) -> bool:
    cancel = cancel or CancellationGuard()
    cancel.checkpoint()
    save_debug(page, "body_fill_dom_before")
    try:
        loc.evaluate(
            """(el, text) => {
                el.scrollIntoView({block: 'center', inline: 'nearest'});
                el.focus();
                const parts = String(text || '').replace(/\r\n?/g, '\n').split(/\n{2,}/);
                const esc = (s) => s
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;');
                el.innerHTML = parts.map(part => {
                    const lines = part.split('\n').map(esc).join('<br>');
                    return `<p>${lines || '<br>'}</p>`;
                }).join('');
                const range = document.createRange();
                range.selectNodeContents(el);
                range.collapse(false);
                const selection = window.getSelection && window.getSelection();
                if (selection) {
                    selection.removeAllRanges();
                    selection.addRange(range);
                }
                for (const type of ['beforeinput', 'input']) {
                    try {
                        el.dispatchEvent(new InputEvent(type, {bubbles: true, cancelable: true, inputType: 'insertText', data: text}));
                    } catch (_) {
                        el.dispatchEvent(new Event(type, {bubbles: true, cancelable: true}));
                    }
                }
                el.dispatchEvent(new Event('change', {bubbles: true}));
                el.blur();
                el.focus();
            }""",
            text,
        )
        cancel.wait_page(page, 350)
        try:
            loc.click(timeout=3000, force=True)
            page.keyboard.press("End")
            page.keyboard.press("Space")
            cancel.wait_page(page, 120)
            page.keyboard.press("Backspace")
        except TaskCancelled:
            raise
        except Exception:
            pass
        cancel.wait_page(page, 350)
        ok = _text_was_written(loc, text)
        save_debug(page, "body_fill_dom_success" if ok else "body_fill_dom_failed")
        return ok
    except TaskCancelled:
        raise
    except Exception:
        save_debug(page, "body_fill_dom_exception")
        return False


def _fill_editable_by_keyboard(
    page: Page,
    loc: Locator,
    text: str,
    *,
    cancel: CancellationGuard | None = None,
) -> bool:
    cancel = cancel or CancellationGuard()
    cancel.checkpoint()
    save_debug(page, "body_fill_keyboard_before")
    try:
        loc.evaluate("el => el.scrollIntoView({block: 'center', inline: 'nearest'})")
    except Exception:
        pass
    try:
        loc.click(timeout=5000, force=True)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.insert_text(text)
        cancel.wait_page(page, 350)
        ok = _text_was_written(loc, text)
        save_debug(page, "body_fill_keyboard_success" if ok else "body_fill_keyboard_failed")
        return ok
    except TaskCancelled:
        raise
    except Exception:
        save_debug(page, "body_fill_keyboard_exception")
        return False


def fill_locator(
    page: Page,
    loc: Locator,
    text: str,
    *,
    cancel: CancellationGuard | None = None,
) -> None:
    cancel = cancel or CancellationGuard()
    cancel.checkpoint()
    try:
        tag = str(loc.evaluate("el => (el.tagName || '').toLowerCase()"))
    except Exception:
        tag = ""
    try:
        is_editable = bool(
            loc.evaluate(
                """el => el.isContentEditable || el.getAttribute('contenteditable') === 'true' ||
                        String(el.className || '').toLowerCase().includes('prosemirror') ||
                        String(el.className || '').toLowerCase().includes('ql-editor') ||
                        String(el.className || '').toLowerCase().includes('drafteditor') ||
                        String(el.className || '').toLowerCase().includes('public-drafteditor') ||
                        el.getAttribute('role') === 'textbox'"""
            )
        )
    except Exception:
        is_editable = False

    if tag in {"input", "textarea"}:
        save_debug(page, "input_fill_before")
        try:
            loc.scroll_into_view_if_needed(timeout=5000)
        except Exception:
            pass
        try:
            loc.fill(text, timeout=5000)
            cancel.wait_page(page, 100)
            if _text_was_written(loc, text):
                save_debug(page, "input_fill_success")
                cancel.checkpoint()
                return
        except TaskCancelled:
            raise
        except Exception:
            pass
        try:
            loc.evaluate(
                """(el, text) => {
                    el.focus();
                    const proto = el.tagName && el.tagName.toLowerCase() === 'textarea'
                        ? window.HTMLTextAreaElement.prototype
                        : window.HTMLInputElement.prototype;
                    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                    if (setter) setter.call(el, text);
                    else el.value = text;
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                }""",
                text,
            )
            cancel.wait_page(page, 100)
            if _text_was_written(loc, text):
                save_debug(page, "input_fill_js_success")
                return
        except TaskCancelled:
            raise
        except Exception:
            pass
        try:
            loc.click(timeout=5000, force=True)
            page.keyboard.press("Control+A")
            page.keyboard.insert_text(text)
            cancel.wait_page(page, 150)
            if _text_was_written(loc, text):
                save_debug(page, "input_fill_keyboard_success")
                return
        except TaskCancelled:
            raise
        except Exception:
            pass
        save_debug(page, "input_fill_all_methods_failed", force=True)
        raise EditorWriteNotReady("标题或章节序号写入失败：页面未接收到输入内容。")

    if is_editable:
        for attempt in range(2):
            cancel.checkpoint()
            if not _wait_for_editable_ready(page, loc, cancel=cancel):
                if attempt == 0:
                    cancel.wait_page(page, 500)
                    continue
                save_debug(page, "body_editor_not_ready", force=True)
                raise EditorWriteNotReady("正文编辑器仍在切换，输入区尚未稳定可写。")
            if _fill_editable_by_paste(page, loc, text, cancel=cancel):
                return
            if _fill_editable_by_dom(page, loc, text, cancel=cancel):
                return
            if _fill_editable_by_keyboard(page, loc, text, cancel=cancel):
                return
            if attempt == 0:
                cancel.wait_page(page, 900)
                try:
                    loc.evaluate("el => { el.blur(); el.focus(); }")
                except Exception:
                    pass
        save_debug(page, "body_fill_all_methods_failed", force=True)
        raise EditorWriteNotReady("正文编辑器写入失败：页面未接收到正文内容。")

    try:
        loc.scroll_into_view_if_needed(timeout=5000)
    except Exception:
        pass
    try:
        loc.click(timeout=5000, force=True)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.insert_text(text)
        cancel.wait_page(page, 150)
        if _text_was_written(loc, text):
            return
    except TaskCancelled:
        raise
    except Exception:
        pass

    try:
        loc.evaluate(
            """(el, text) => {
                el.focus();
                if ('value' in el) {
                    el.value = text;
                } else {
                    el.innerText = text;
                    el.textContent = text;
                }
                el.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: text}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
            }""",
            text,
        )
        cancel.wait_page(page, 150)
        if _text_was_written(loc, text):
            return
    except TaskCancelled:
        raise
    except Exception:
        pass
    raise EditorWriteNotReady("编辑器输入区已失效，页面未接收到输入内容。")
