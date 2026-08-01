from __future__ import annotations

import pytest

from backend.platforms.fanqie import book_identity


class FakeBody:
    def __init__(self, text: str) -> None:
        self._text = text

    def inner_text(self, timeout: int = 0) -> str:
        return self._text


class FakeHeadings:
    def all_inner_texts(self) -> list[str]:
        return []


class FakePage:
    def __init__(self, url: str, text: str) -> None:
        self.url = url
        self._text = text

    def locator(self, selector: str):
        return FakeBody(self._text) if selector == "body" else FakeHeadings()


def _disable_navigation(monkeypatch) -> None:
    monkeypatch.setattr(book_identity, "goto_chapter_manage", lambda *args, **kwargs: None)
    monkeypatch.setattr(book_identity, "ensure_logged_in", lambda *args, **kwargs: None)


def test_book_identity_accepts_matching_url_and_visible_page_title(monkeypatch) -> None:
    _disable_navigation(monkeypatch)
    url = "https://fanqienovel.com/main/writer/chapter-manage/123&修仙：写个日记，女主们不对劲了?type=1"
    page = FakePage(url, "作品管理\n修仙：写个日记，女主们不对劲了\n章节管理\n草稿箱")
    logs: list[str] = []

    actual = book_identity.verify_chapter_manage_book(
        page, url, "修仙：写个日记，女主们不对劲了", log=logs.append
    )

    assert actual == "修仙：写个日记，女主们不对劲了"
    assert any("校验通过" in message for message in logs)


def test_book_identity_blocks_when_visible_page_is_another_book(monkeypatch) -> None:
    _disable_navigation(monkeypatch)
    url = "https://fanqienovel.com/main/writer/chapter-manage/123"
    page = FakePage(url, "作品管理\n反派：她们怎么还偷看我日记？！\n章节管理\n草稿箱")

    with pytest.raises(RuntimeError, match="当前番茄页面实际为"):
        book_identity.verify_chapter_manage_book(page, url, "修仙：写个日记，女主们不对劲了")


def test_book_identity_rejects_book_manage_list_url(monkeypatch) -> None:
    _disable_navigation(monkeypatch)
    url = "https://fanqienovel.com/main/writer/book-manage"
    page = FakePage(url, "作品管理")

    with pytest.raises(RuntimeError, match="具体作品的番茄章节管理 URL"):
        book_identity.verify_chapter_manage_book(page, url, "测试小说")


class FakeBookLinks:
    def evaluate_all(self, _script: str) -> list[str]:
        return [
            "https://fanqienovel.com/main/writer/chapter-manage/123&第一本书?type=1",
            "https://fanqienovel.com/main/writer/chapter-manage/456&第二本书?type=1",
            "https://fanqienovel.com/main/writer/chapter-manage/123&第一本书?type=1",
        ]


class FakeBookManagePage:
    def goto(self, *_args, **_kwargs) -> None:
        pass

    def wait_for_timeout(self, _timeout: int) -> None:
        pass

    def locator(self, _selector: str) -> FakeBookLinks:
        return FakeBookLinks()


def test_collect_book_manage_entries_reads_unique_chapter_links(monkeypatch) -> None:
    monkeypatch.setattr(book_identity, "ensure_logged_in", lambda *args, **kwargs: None)

    books = book_identity.collect_book_manage_entries(FakeBookManagePage())

    assert [(book["bookId"], book["name"]) for book in books] == [("123", "第一本书"), ("456", "第二本书")]
