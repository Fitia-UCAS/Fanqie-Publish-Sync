from __future__ import annotations

from typing import Optional, Tuple
import re

from playwright.sync_api import Locator, Page

from backend.features.novel_processing.text_normalizer import normalize_novel_body, normalize_text
from backend.platforms.fanqie.text_utils import count_non_whitespace_chars
from backend.platforms.fanqie.actions.navigation import click_next_page, click_page_number, get_visible_page_numbers
from backend.platforms.fanqie.actions.interactions import dismiss_popups, ensure_logged_in, goto_chapter_manage, locator_count_safe, wait_briefly_for_page_ready
from backend.platforms.fanqie.dialogs.editing import click_continue_edit_if_present
from backend.platforms.fanqie.browser.session import save_debug


class ChapterEditorNotFound(RuntimeError):
    def __init__(self, chapter_no: int) -> None:
        super().__init__(f"未能在番茄章节管理列表中定位到第 {chapter_no} 章。")
        self.chapter_no = chapter_no


def click_edit_near_chapter_by_js(page: Page, targets: list[str]) -> bool:
    script = r"""
    (targets) => {
        function visible(el) {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            return rect.width > 0 && rect.height > 0 &&
                   style.visibility !== 'hidden' && style.display !== 'none';
        }
        function includesTarget(text) {
            if (!text) return false;
            const compact = text.replace(/\s+/g, '');
            return targets.some(t => {
                const tt = String(t || '').replace(/\s+/g, '');
                return tt && compact.includes(tt);
            });
        }
        const rows = Array.from(document.querySelectorAll('tr, .arco-table-tr')).filter(visible);
        for (const row of rows) {
            const text = row.innerText || row.textContent || '';
            if (!includesTarget(text)) continue;
            const link = row.querySelector('a[href*="/publish/"][href*="modifychapter"]')
                      || row.querySelector('a[href*="/publish/"]')
                      || row.querySelector('a.link');
            if (link) {
                link.scrollIntoView({block: 'center', inline: 'center'});
                window.location.href = link.href;
                return {ok: true, href: link.href};
            }
            const icon = row.querySelector('.icon-edit, .tomato-edit, [class*="edit"]');
            if (icon) {
                const a = icon.closest('a');
                if (a && a.href) {
                    a.scrollIntoView({block: 'center', inline: 'center'});
                    window.location.href = a.href;
                    return {ok: true, href: a.href};
                }
                icon.click();
                return {ok: true};
            }
        }
        return {ok: false};
    }
    """
    try:
        result = page.evaluate(script, targets)
        return bool(isinstance(result, dict) and result.get("ok"))
    except Exception:
        return False

def open_chapter_editor(
    page: Page,
    chapter_manage_url: str,
    chapter_no: int,
    local_title: str,
    log=print,
    cached_editor_url: Optional[str] = None,
    manual_fallback: bool = False,
) -> None:
    log(f"正在定位番茄后台第 {chapter_no} 章...")
    if cached_editor_url:
        try:
            log("使用已缓存的章节入口，直接进入编辑页...")
            page.goto(cached_editor_url, wait_until="domcontentloaded", timeout=60000)
            wait_briefly_for_page_ready(page)
            click_continue_edit_if_present(page, log=log, timeout_ms=1500)
            return
        except Exception:
            log("缓存入口打开失败，改用常规定位方式...")
    goto_chapter_manage(page, chapter_manage_url)
    ensure_logged_in(page, chapter_manage_url, log=log)
    dismiss_popups(page)


    targets = [
        f"第{chapter_no}章 {local_title}",
        f"第 {chapter_no} 章 {local_title}",
        f"第{chapter_no}章",
        f"第 {chapter_no} 章",
        local_title,
    ]
    def try_current_page() -> bool:
        for _ in range(2):
            if click_edit_near_chapter_by_js(page, targets):
                page.wait_for_timeout(1500)
                click_continue_edit_if_present(page, log=log, timeout_ms=2000)
                return True
            page.wait_for_timeout(700)
        return False

    if try_current_page():
        return

    visited_pages: set[int] = set()
    for _ in range(40):
        progressed = False
        page_numbers = sorted(get_visible_page_numbers(page))
        for page_no in page_numbers:
            if page_no in visited_pages:
                continue
            visited_pages.add(page_no)
            if click_page_number(page, page_no):
                progressed = True
                dismiss_popups(page)
                if try_current_page():
                    return
        if click_next_page(page):
            progressed = True
            dismiss_popups(page)
            if try_current_page():
                return
        if not progressed:
            break

    goto_chapter_manage(page, chapter_manage_url)
    page.wait_for_timeout(1500)
    visited_pages.clear()
    for _ in range(40):
        progressed = False
        page_numbers = sorted(get_visible_page_numbers(page))
        for page_no in page_numbers:
            if page_no in visited_pages:
                continue
            visited_pages.add(page_no)
            if click_page_number(page, page_no):
                progressed = True
                if try_current_page():
                    return
        if click_next_page(page):
            progressed = True
            if try_current_page():
                return
        if not progressed:
            break
    if manual_fallback:
        log("自动定位章节失败，请手动点进目标章节编辑页。")
        input("看到标题框、正文编辑器、保存按钮后按 Enter：")
        page.wait_for_timeout(1000)
        click_continue_edit_if_present(page, log=log, timeout_ms=1500)
        return
    raise ChapterEditorNotFound(chapter_no)

def all_input_like(page: Page) -> list[Locator]:
    selectors = [
        "input",
        "textarea",
        "[contenteditable='true']",
        "[contenteditable=true]",
        ".ProseMirror",
        ".ql-editor",
        ".DraftEditor-root",
        ".public-DraftEditor-content",
        "[role='textbox']",
    ]
    result: list[Locator] = []
    for sel in selectors:
        loc = page.locator(sel)
        count = locator_count_safe(loc)
        for i in range(count):
            item = loc.nth(i)
            try:
                if item.is_visible():
                    result.append(item)
            except Exception:
                continue
    return result

def element_text_or_value(loc: Locator) -> str:
    try:
        tag = loc.evaluate("el => el.tagName.toLowerCase()")
    except Exception:
        tag = ""
    try:
        if tag in ("input", "textarea"):
            return loc.input_value(timeout=3000)
    except Exception:
        pass
    try:
        value = loc.evaluate(
            """el => {
                if ('value' in el && el.value) return el.value;
                return el.innerText || el.textContent || '';
            }"""
        )
        return value or ""
    except Exception:
        return ""


def reported_body_word_count(page: Page) -> int | None:
    try:
        body = page.locator("body").inner_text(timeout=1000)
    except Exception:
        body = ""
    if not body:
        return None
    compact = re.sub(r"\s+", "", body)
    matches = [int(m.group(1)) for m in re.finditer(r"正文字数[:：]?(\d{1,8})", compact)]
    if not matches:
        matches = [int(m.group(1)) for m in re.finditer(r"正文(?:字数|字数统计)[:：]?(\d{1,8})", compact)]
    if not matches:
        return None
    return max(matches)


def editor_body_counter_confirms(page: Page, text: str) -> bool:
    count = reported_body_word_count(page)
    if count is None:
        return False
    expected = count_non_whitespace_chars(normalize_novel_body(text or ""))
    if expected <= 0:
        return True
    if expected >= 400:
        floor = max(200, int(expected * 0.45))
    elif expected >= 80:
        floor = max(40, int(expected * 0.45))
    else:
        floor = max(1, int(expected * 0.45))
    return count >= floor


def _input_meta(loc: Locator) -> dict:
    try:
        return loc.evaluate(
            """el => {
                const tag = (el.tagName || '').toLowerCase();
                const cls = String(el.className || '').toLowerCase();
                const placeholder = String(el.getAttribute('placeholder') || '').trim();
                const aria = String(el.getAttribute('aria-label') || '').trim();
                const role = String(el.getAttribute('role') || '').trim();
                const type = String(el.getAttribute('type') || '').toLowerCase();
                const contenteditable = el.isContentEditable || el.getAttribute('contenteditable') === 'true';
                const text = ('value' in el && el.value !== undefined) ? el.value : (el.innerText || el.textContent || '');
                const rect = el.getBoundingClientRect();
                const parentText = (el.parentElement && (el.parentElement.innerText || el.parentElement.textContent)) || '';
                const hint = `${placeholder} ${aria} ${cls} ${parentText}`.toLowerCase();
                const editorLike = contenteditable || role === 'textbox' ||
                    cls.includes('prosemirror') || cls.includes('ql-editor') ||
                    cls.includes('drafteditor') || cls.includes('public-drafteditor');
                const bodyHint = hint.includes('正文') || hint.includes('content') || hint.includes('请输入正文') || cls.includes('prosemirror') || cls.includes('ql-editor');
                return {
                    tag, cls, placeholder, aria, role, type, contenteditable,
                    text: String(text || ''), editorLike, bodyHint,
                    width: rect.width || 0, height: rect.height || 0,
                    area: Math.max(0, (rect.width || 0) * (rect.height || 0))
                };
            }"""
        )
    except Exception:
        return {}


def _locator_is(loc: Locator, expected: Locator) -> bool:
    try:
        return bool(loc.evaluate("(el, other) => el === other", expected.element_handle()))
    except Exception:
        return loc is expected


def _looks_like_chapter_no_value(value: str) -> bool:
    value = (value or "").strip()
    return value.isdigit() and len(value) <= 4


def _looks_like_no_field(meta: dict) -> bool:
    text = " ".join(str(meta.get(key) or "") for key in ("placeholder", "aria", "cls", "type"))
    compact = "".join(text.split()).lower()
    return any(word in compact for word in ("章节序号", "章序号", "章节号", "章号", "序号", "chapterindex", "chapterno", "chapter-no"))


def _looks_like_title_field(meta: dict) -> bool:
    text = " ".join(str(meta.get(key) or "") for key in ("placeholder", "aria", "cls"))
    compact = "".join(text.split()).lower()
    return any(word in compact for word in ("请输入标题", "请输入章节名", "章节名", "主标题", "标题", "chaptertitle", "title"))


def pick_title_and_editor(page: Page) -> Tuple[Locator, Locator]:
    _chapter_no_loc, title_loc, body_loc = pick_chapter_no_title_and_editor(page, require_chapter_no=False)
    return title_loc, body_loc


def pick_chapter_no_title_and_editor(page: Page, *, require_chapter_no: bool = True) -> tuple[Locator | None, Locator, Locator]:
    candidates = all_input_like(page)
    if not candidates:
        raise RuntimeError("未找到任何输入框或正文编辑器。请确认已经进入章节编辑页。")

    scored = []
    for loc in candidates:
        meta = _input_meta(loc)
        txt = str(meta.get("text") or element_text_or_value(loc))
        txt_norm = normalize_text(txt)
        tag = str(meta.get("tag") or "")
        editor_like = bool(meta.get("editorLike")) and tag not in {"input", "textarea"}
        scored.append({
            "length": len(txt_norm),
            "tag": tag,
            "loc": loc,
            "txt_norm": txt_norm,
            "meta": meta,
            "editor_like": editor_like,
        })


    def body_score(item: dict) -> tuple[int, int, int, int, int]:
        meta = item["meta"]
        tag = item["tag"]
        area = int(float(meta.get("area") or 0))
        height = int(float(meta.get("height") or 0))
        body_hint = bool(meta.get("bodyHint"))
        return (
            1 if item["editor_like"] else 0,
            1 if body_hint else 0,
            0 if tag in {"input", "textarea"} else 1,
            area,
            height + item["length"],
        )

    body_item = max(scored, key=body_score)
    body_loc = body_item["loc"]

    non_body = [item for item in scored if not _locator_is(item["loc"], body_loc)]

    def title_score(item: dict) -> tuple[int, int, int]:
        meta = item["meta"]
        tag = item["tag"]
        value = item["txt_norm"]
        if tag not in {"input", "textarea"}:
            return (99, 0, 0)
        if _looks_like_no_field(meta) or _looks_like_chapter_no_value(value):
            return (30, 0, 0)
        if _looks_like_title_field(meta):
            return (0, -item["length"], 0)
        if item["length"] <= 120:
            return (8 if item["length"] == 0 else 4, -item["length"], 0)
        return (60, -item["length"], 0)

    title_items = sorted(non_body, key=title_score)
    title_item = next((item for item in title_items if title_score(item)[0] < 60), None)
    if not title_item:
        raise RuntimeError("找到了正文编辑器，但未能识别标题输入框。")
    title_loc = title_item["loc"]

    chapter_no_loc: Locator | None = None
    if require_chapter_no:
        no_items = []
        for item in non_body:
            if _locator_is(item["loc"], title_loc):
                continue
            meta = item["meta"]
            tag = item["tag"]
            if tag not in {"input", "textarea"}:
                continue
            score = 50
            if _looks_like_no_field(meta):
                score = 0
            elif _looks_like_chapter_no_value(item["txt_norm"]):
                score = 3
            elif item["length"] == 0:
                score = 8
            if score < 50:
                no_items.append((score, item))
        if no_items:
            chapter_no_loc = min(no_items, key=_chapter_no_candidate_score)[1]["loc"]
        else:
            raise RuntimeError("新建章节页已打开，但未能识别章节序号输入框。")

    return chapter_no_loc, title_loc, body_loc


def _chapter_no_candidate_score(pair) -> int:
    return pair[0]

def get_remote_chapter(page: Page) -> tuple[str, str, Locator, Locator]:
    title_loc, body_loc = pick_title_and_editor(page)
    remote_title = element_text_or_value(title_loc).strip()


    remote_body = normalize_novel_body(element_text_or_value(body_loc))
    return remote_title, remote_body, title_loc, body_loc


def _wait_for_editable_ready(page: Page, loc: Locator, *, timeout_ms: int = 8000) -> None:
    try:
        loc.wait_for(state="visible", timeout=timeout_ms)
    except Exception:
        pass
    try:
        loc.evaluate(
            """el => new Promise(resolve => {
                const started = Date.now();
                const ready = () => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    const editable = el.isContentEditable ||
                        el.getAttribute('contenteditable') === 'true' ||
                        String(el.className || '').toLowerCase().includes('prosemirror') ||
                        String(el.className || '').toLowerCase().includes('ql-editor') ||
                        el.getAttribute('role') === 'textbox';
                    return editable && rect.width > 0 && rect.height > 0 &&
                        style.visibility !== 'hidden' && style.display !== 'none' &&
                        !el.hasAttribute('disabled') && el.getAttribute('aria-disabled') !== 'true';
                };
                const tick = () => {
                    if (ready() || Date.now() - started > 7500) {
                        resolve(true);
                        return;
                    }
                    requestAnimationFrame(tick);
                };
                tick();
            })"""
        )
    except Exception:
        pass
    try:
        loc.evaluate("el => { el.scrollIntoView({block: 'center', inline: 'nearest'}); el.focus(); }")
    except Exception:
        pass
    page.wait_for_timeout(300)


def _editable_text(loc: Locator) -> str:
    try:
        value = loc.evaluate("el => el.innerText || el.textContent || ''")
        return str(value or "")
    except Exception:
        return ""


def _text_was_written(loc: Locator, text: str) -> bool:
    expected = normalize_text(text)
    current = normalize_text(_editable_text(loc))
    if not expected:
        return True
    if len(expected) < 80:
        return current == expected or expected in current

    return len(current) >= max(80, int(len(expected) * 0.65)) and expected[:40] in current and expected[-40:] in current


def _fill_editable_by_paste(page: Page, loc: Locator, text: str) -> bool:
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
        page.wait_for_timeout(450)

        page.keyboard.press("End")
        page.keyboard.press("Space")
        page.wait_for_timeout(120)
        page.keyboard.press("Backspace")
        page.wait_for_timeout(350)
        ok = _text_was_written(loc, text) or editor_body_counter_confirms(page, text)
        save_debug(page, "body_fill_paste_success" if ok else "body_fill_paste_failed")
        return ok
    except Exception:
        save_debug(page, "body_fill_paste_exception")
        return False


def _fill_editable_by_dom(page: Page, loc: Locator, text: str) -> bool:
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
        page.wait_for_timeout(350)
        try:
            loc.click(timeout=3000, force=True)
            page.keyboard.press("End")
            page.keyboard.press("Space")
            page.wait_for_timeout(120)
            page.keyboard.press("Backspace")
        except Exception:
            pass
        page.wait_for_timeout(350)
        ok = _text_was_written(loc, text) or editor_body_counter_confirms(page, text)
        save_debug(page, "body_fill_dom_success" if ok else "body_fill_dom_failed")
        return ok
    except Exception:
        save_debug(page, "body_fill_dom_exception")
        return False


def _fill_editable_by_keyboard(page: Page, loc: Locator, text: str) -> bool:
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
        page.wait_for_timeout(350)
        ok = _text_was_written(loc, text) or editor_body_counter_confirms(page, text)
        save_debug(page, "body_fill_keyboard_success" if ok else "body_fill_keyboard_failed")
        return ok
    except Exception:
        save_debug(page, "body_fill_keyboard_exception")
        return False


def fill_locator(page: Page, loc: Locator, text: str) -> None:
    try:
        tag = str(loc.evaluate("el => (el.tagName || '').toLowerCase()"))
    except Exception:
        tag = ""
    try:
        is_editable = bool(
            loc.evaluate(
                """el => el.isContentEditable || el.getAttribute('contenteditable') === 'true' ||
                        String(el.className || '').toLowerCase().includes('prosemirror') ||
                        String(el.className || '').toLowerCase().includes('ql-editor')"""
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
            loc.fill(text, timeout=30000)
            save_debug(page, "input_fill_success")
            return
        except Exception:
            pass
        try:
            loc.evaluate(
                """(el, text) => {
                    el.focus();
                    el.value = text;
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                }""",
                text,
            )
            save_debug(page, "input_fill_js_success")
            return
        except Exception:
            pass

    if is_editable:
        for attempt in range(2):
            _wait_for_editable_ready(page, loc)
            if _fill_editable_by_paste(page, loc, text):
                return
            if _fill_editable_by_dom(page, loc, text):
                return
            if _fill_editable_by_keyboard(page, loc, text):
                return
            if attempt == 0:
                page.wait_for_timeout(900)
                try:
                    loc.evaluate("el => { el.blur(); el.focus(); }")
                except Exception:
                    pass
        save_debug(page, "body_fill_all_methods_failed", force=True)
        raise RuntimeError("正文编辑器写入失败：页面未接收到正文内容。")

    try:
        loc.scroll_into_view_if_needed(timeout=5000)
    except Exception:
        pass
    try:
        loc.click(timeout=5000, force=True)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.insert_text(text)
        return
    except Exception:
        pass

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


def wait_for_editor_saved(page: Page, *, timeout_ms: int = 15000) -> bool:
    end_rounds = max(1, timeout_ms // 500)
    saw_saving = False
    saw_any_state = False
    for _ in range(end_rounds):
        try:
            body = page.locator("body").inner_text(timeout=800)
        except Exception:
            body = ""
        compact = re.sub(r"\s+", "", body or "")
        if "保存中" in compact:
            saw_saving = True
            saw_any_state = True
            page.wait_for_timeout(500)
            continue
        if "已保存" in compact or "保存成功" in compact:
            return True
        if "保存失败" in compact:
            return False
        page.wait_for_timeout(500)

    return not saw_any_state or not saw_saving


def click_save_draft(page: Page, log=print) -> None:
    save_debug(page, "save_draft_before")
    save_words = ["保存草稿", "保存", "存草稿", "确认保存"]
    for word in save_words:
        loc = page.get_by_text(word, exact=False)
        count = locator_count_safe(loc)
        for i in range(count):
            item = loc.nth(i)
            try:
                if item.is_visible() and item.is_enabled():
                    item.scroll_into_view_if_needed()
                    text = (item.inner_text(timeout=1000) or "").strip()
                    if "发布" in text:
                        continue
                    item.click(timeout=10000)
                    save_debug(page, "save_draft_clicked")
                    page.wait_for_timeout(800)
                    if not wait_for_editor_saved(page, timeout_ms=15000):
                        save_debug(page, "save_draft_state_failed", force=True)
                        raise RuntimeError("保存草稿后未等到“已保存”状态。")
                    save_debug(page, "save_draft_after")
                    return
            except Exception:
                continue
    save_debug(page, "save_draft_button_not_found", force=True)
    raise RuntimeError("未找到保存草稿/保存按钮。")
