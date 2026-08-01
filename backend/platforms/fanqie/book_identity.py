from __future__ import annotations

import re
import unicodedata
from typing import Callable
from urllib.parse import unquote, urlparse

from playwright.sync_api import Page

from backend.platforms.fanqie.actions.interactions import ensure_logged_in, goto_chapter_manage, page_text


CHAPTER_MANAGE_PATH = re.compile(r"/main/writer/chapter-manage/([^/?#]+)", re.IGNORECASE)
BOOK_MANAGE_URL = "https://fanqienovel.com/main/writer/book-manage"


def normalize_book_name(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", "", text).strip()


def verify_chapter_manage_book(
    page: Page,
    chapter_manage_url: str,
    expected_book_name: str,
    *,
    log: Callable[[str], None] = print,
) -> str:
    expected = str(expected_book_name or "").strip()
    if not expected:
        raise RuntimeError("书籍安全校验失败：没有配置预期作品名，已禁止执行。")
    page_title = detect_chapter_manage_book(page, chapter_manage_url, log=log)

    final_url = str(page.url or chapter_manage_url)
    url_title = _book_name_from_url(final_url) or _book_name_from_url(chapter_manage_url)
    normalized_expected = normalize_book_name(expected)
    if url_title and normalize_book_name(url_title) != normalized_expected:
        raise RuntimeError(
            f"书籍安全校验失败：配置作品为《{expected}》，但章节 URL 对应《{url_title}》，已禁止执行。"
        )
    if normalize_book_name(page_title) != normalized_expected:
        raise RuntimeError(
            f"书籍安全校验失败：配置作品为《{expected}》，当前番茄页面实际为《{page_title}》，已禁止执行。"
        )

    log(f"书籍安全校验通过：本地配置、章节 URL 与番茄页面均对应《{expected}》。")
    return page_title


def detect_chapter_manage_book(
    page: Page,
    chapter_manage_url: str,
    *,
    log: Callable[[str], None] = print,
) -> str:
    parsed_url = urlparse(chapter_manage_url)
    if parsed_url.scheme not in {"http", "https"} or not _is_fanqie_host(parsed_url.hostname or ""):
        raise RuntimeError("书籍安全校验失败：章节管理 URL 不是番茄小说网站，已禁止执行。")
    if not CHAPTER_MANAGE_PATH.search(chapter_manage_url):
        raise RuntimeError("书籍安全校验失败：请填写具体作品的番茄章节管理 URL，而不是作品管理列表或其他页面。")

    goto_chapter_manage(page, chapter_manage_url)
    ensure_logged_in(page, chapter_manage_url, log=log)

    final_url = str(page.url or chapter_manage_url)
    final_parsed = urlparse(final_url)
    if not _is_fanqie_host(final_parsed.hostname or "") or not CHAPTER_MANAGE_PATH.search(final_url):
        raise RuntimeError(f"书籍安全校验失败：页面没有停留在章节管理页（{final_url}），已禁止执行。")

    page_title = _book_name_from_page(page)
    if not page_title:
        raise RuntimeError("书籍安全校验失败：无法从番茄章节管理页面读取作品名，已禁止执行。")
    log(f"已从番茄章节管理页读取作品：《{page_title}》。")
    return page_title


def chapter_manage_book_id(value: str) -> str:
    match = CHAPTER_MANAGE_PATH.search(urlparse(value).path)
    if not match:
        return ""
    return unquote(match.group(1)).split("&", 1)[0].strip()


def collect_book_manage_entries(
    page: Page,
    *,
    log: Callable[[str], None] = print,
) -> list[dict[str, str]]:
    page.goto(BOOK_MANAGE_URL, wait_until="domcontentloaded", timeout=60000)
    ensure_logged_in(page, BOOK_MANAGE_URL, log=log)
    page.wait_for_timeout(1800)
    try:
        hrefs = page.locator('a[href*="/main/writer/chapter-manage/"]').evaluate_all(
            "elements => elements.map(element => element.href).filter(Boolean)"
        )
    except Exception as exc:
        raise RuntimeError(f"无法读取番茄作品列表：{exc}") from exc
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_url in hrefs or []:
        url = str(raw_url or "").strip()
        book_id = chapter_manage_book_id(url)
        name = _book_name_from_url(url)
        if not book_id or not name or book_id in seen:
            continue
        seen.add(book_id)
        entries.append({"id": f"fanqie-{book_id}", "bookId": book_id, "name": name, "chapterManageUrl": url})
    if not entries:
        raise RuntimeError("没有从番茄作品管理页读取到作品。")
    log(f"已读取 {len(entries)} 本番茄作品。")
    return entries


def _book_name_from_url(value: str) -> str:
    match = CHAPTER_MANAGE_PATH.search(urlparse(value).path)
    if not match:
        return ""
    segment = unquote(match.group(1))
    if "&" not in segment:
        return ""
    return segment.split("&", 1)[1].strip()


def _book_name_from_page(page: Page) -> str:
    lines = [line.strip() for line in page_text(page, limit=12000).splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if normalize_book_name(line) != "章节管理":
            continue
        for candidate in reversed(lines[max(0, index - 3):index]):
            if _looks_like_book_name(candidate):
                return candidate
    try:
        headings = page.locator("h1, h2, h3").all_inner_texts()
    except Exception:
        headings = []
    for candidate in headings:
        value = str(candidate or "").strip()
        if _looks_like_book_name(value):
            return value
    return ""


def _looks_like_book_name(value: str) -> bool:
    compact = normalize_book_name(value)
    return bool(compact) and len(compact) <= 100 and compact not in {
        "作品管理", "小说", "短故事", "草稿箱", "审核状态", "全部", "工作台"
    }


def _is_fanqie_host(hostname: str) -> bool:
    host = str(hostname or "").lower().rstrip(".")
    return host == "fanqienovel.com" or host.endswith(".fanqienovel.com")
