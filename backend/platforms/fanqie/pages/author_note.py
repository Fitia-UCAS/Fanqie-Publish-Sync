from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Locator, Page

from backend.platforms.fanqie.actions.interactions import locator_count_safe
from backend.runtime.errors import TaskCancelled
from backend.runtime.jobs.cancellation import CancellationGuard


_EDITOR_SELECTORS = (
    "textarea",
    "[contenteditable='true']",
    ".ProseMirror",
    ".ql-editor",
    "[role='textbox']",
)


def _author_note_is_empty(page: Page) -> bool:
    labels = page.get_by_text("作者有话说", exact=True)
    for index in range(locator_count_safe(labels)):
        item = labels.nth(index)
        try:
            if not item.is_visible():
                continue
            if item.evaluate(
                r"""el => {
                    const compact = node => String(node.innerText || node.textContent || '').replace(/\s+/g, '').trim();
                    const visible = node => {
                        const rect = node.getBoundingClientRect();
                        const style = window.getComputedStyle(node);
                        return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
                    };
                    let root = el;
                    for (let depth = 0; root && depth <= 7; depth += 1, root = root.parentElement) {
                        const rootText = compact(root);
                        if (!rootText.includes('作者有话说') || rootText.length > 1200) continue;
                        const nodes = Array.from(root.querySelectorAll('button, [role="button"], a, span, div'));
                        if (nodes.some(node => {
                            const text = compact(node);
                            return visible(node) && text.endsWith('添加') && text.length <= 3;
                        })) return true;
                    }
                    return false;
                }"""
            ):
                return True
        except Exception:
            continue
    return False


def _author_note_editor(page: Page) -> Locator | None:
    candidates: list[tuple[int, int, Locator]] = []
    for selector in _EDITOR_SELECTORS:
        locators = page.locator(selector)
        for index in range(locator_count_safe(locators)):
            item = locators.nth(index)
            try:
                if not item.is_visible():
                    continue
                meta = item.evaluate(
                    r"""el => {
                        let node = el;
                        for (let depth = 0; node && depth <= 9; depth += 1, node = node.parentElement) {
                            const text = String(node.innerText || node.textContent || '').replace(/\s+/g, '').trim();
                            const visible = child => {
                                const rect = child.getBoundingClientRect();
                                const style = window.getComputedStyle(child);
                                return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
                            };
                            const actions = Array.from(node.querySelectorAll('button, [role="button"], a'));
                            const actionTexts = actions.filter(visible).map(child => String(child.innerText || child.textContent || '').replace(/\s+/g, '').trim());
                            if (text.includes('作者有话说') && text.length <= 2500 && actionTexts.includes('保存') && actionTexts.includes('退出')) {
                                return {depth, length: text.length};
                            }
                        }
                        return null;
                    }"""
                )
            except Exception:
                continue
            if meta:
                candidates.append((int(meta.get("depth", 99)), int(meta.get("length", 99999)), item))
    if not candidates:
        return None
    return min(candidates, key=lambda item: (item[0], item[1]))[2]


def _open_author_note(page: Page, cancel: CancellationGuard) -> None:
    try:
        labels = page.get_by_text("作者有话说", exact=True)
        for index in range(locator_count_safe(labels)):
            item = labels.nth(index)
            if item.is_visible():
                item.click(timeout=3000, force=True)
                cancel.wait_page(page, 500)
                return
    except TaskCancelled:
        raise
    except Exception:
        pass


def _clear_editor(page: Page, editor: Locator, cancel: CancellationGuard) -> None:
    cancel.checkpoint()
    try:
        editor.evaluate(
            """el => {
                el.scrollIntoView({block: 'center', inline: 'nearest'});
                el.focus();
                const tag = String(el.tagName || '').toLowerCase();
                if (tag === 'textarea' || tag === 'input') {
                    const owner = tag === 'textarea' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                    const setter = Object.getOwnPropertyDescriptor(owner, 'value')?.set;
                    if (setter) setter.call(el, '');
                    else el.value = '';
                } else {
                    el.innerHTML = '<p><br></p>';
                }
                try {
                    el.dispatchEvent(new InputEvent('beforeinput', {
                        bubbles: true, cancelable: true, inputType: 'deleteContentBackward', data: null
                    }));
                    el.dispatchEvent(new InputEvent('input', {
                        bubbles: true, cancelable: true, inputType: 'deleteContentBackward', data: null
                    }));
                } catch (_) {
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                }
                el.dispatchEvent(new Event('change', {bubbles: true}));
            }"""
        )
        cancel.wait_page(page, 250)
    except TaskCancelled:
        raise
    except Exception:
        pass

    if _editor_value(editor).strip():
        try:
            editor.click(timeout=3000, force=True)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            cancel.wait_page(page, 250)
        except TaskCancelled:
            raise
        except Exception:
            pass
    if _editor_value(editor).strip():
        raise RuntimeError("“作者有话说”清空失败，已停止本章，避免把旧内容继续提交。")


def _editor_value(editor: Locator) -> str:
    try:
        return str(
            editor.evaluate(
                "el => ('value' in el ? el.value : (el.innerText || el.textContent || '')) || ''"
            )
            or ""
        )
    except Exception:
        return ""


def _click_section_action(editor: Locator, action_text: str) -> bool:
    try:
        return bool(
            editor.evaluate(
                r"""(el, actionText) => {
                    const compact = node => String(node.innerText || node.textContent || '').replace(/\s+/g, '').trim();
                    const visible = node => {
                        const rect = node.getBoundingClientRect();
                        const style = window.getComputedStyle(node);
                        return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
                    };
                    let root = el;
                    for (let depth = 0; root && depth <= 9; depth += 1, root = root.parentElement) {
                        const rootText = compact(root);
                        if (!rootText.includes('作者有话说') || rootText.length > 2500) continue;
                        const nodes = Array.from(root.querySelectorAll('button, [role="button"], a, span, div'));
                        const match = nodes.find(node => visible(node) && compact(node) === actionText);
                        if (!match) continue;
                        const target = match.closest('button, [role="button"], a') || match;
                        target.scrollIntoView({block: 'center', inline: 'nearest'});
                        target.click();
                        return true;
                    }
                    return false;
                }""",
                action_text,
            )
        )
    except Exception:
        return False


def clear_author_note_and_save(
    page: Page,
    *,
    log: Callable[[str], None] = print,
    cancel: CancellationGuard | None = None,
) -> None:
    cancel = cancel or CancellationGuard()
    cancel.checkpoint()
    if _author_note_is_empty(page):
        log("“作者有话说”当前为空，无需清理。")
        return
    editor = _author_note_editor(page)
    if editor is None:
        _open_author_note(page, cancel)
        editor = _author_note_editor(page)
    if editor is None:
        raise RuntimeError("已勾选“清空作者有话说”，但编辑页中没有找到该输入区，已停止本章。")

    if not _editor_value(editor).strip():
        log("“作者有话说”当前为空，无需清理。")
        _click_section_action(editor, "退出")
        cancel.wait_page(page, 300)
        return

    log("正在清空并单独保存“作者有话说”...")
    _clear_editor(page, editor, cancel)
    cancel.checkpoint()
    if not _click_section_action(editor, "保存"):
        raise RuntimeError("“作者有话说”已经清空，但没有找到它自己的“保存”按钮，已停止本章。")
    cancel.wait_page(page, 1200)
    cancel.checkpoint()
    _click_section_action(editor, "退出")
    cancel.wait_page(page, 300)
    log("“作者有话说”已清空并保存。")


__all__ = ["clear_author_note_and_save"]
