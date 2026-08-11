from __future__ import annotations

import pytest

from backend.platforms.fanqie.pages import editor_fields


class _Candidate:
    def __init__(self, visible: bool) -> None:
        self.visible = visible

    def is_visible(self) -> bool:
        return self.visible


class _CandidateCollection:
    def __init__(self, candidates: list[_Candidate]) -> None:
        self.candidates = candidates

    def count(self) -> int:
        return len(self.candidates)

    def nth(self, index: int) -> _Candidate:
        return self.candidates[index]


class _Page:
    def __init__(self) -> None:
        self.selectors: list[str] = []
        self.collection = _CandidateCollection([_Candidate(True), _Candidate(False), _Candidate(True)])

    def locator(self, selector: str) -> _CandidateCollection:
        self.selectors.append(selector)
        return self.collection


def test_input_candidates_are_collected_with_one_deduplicating_dom_query() -> None:
    page = _Page()

    candidates = editor_fields.all_input_like(page)

    assert len(candidates) == 2
    assert len(page.selectors) == 1
    assert "input, textarea" in page.selectors[0]
    assert ".ProseMirror" in page.selectors[0]


def test_existing_editor_with_blank_title_is_treated_as_not_ready(monkeypatch) -> None:
    title_loc = object()
    body_loc = object()
    monkeypatch.setattr(editor_fields, "pick_title_and_editor", lambda _page: (title_loc, body_loc))
    monkeypatch.setattr(editor_fields, "element_text_or_value", lambda loc: "" if loc is title_loc else "正文")

    with pytest.raises(editor_fields.EditorFieldsNotReady, match="标题输入框尚未加载"):
        editor_fields.get_remote_chapter(object())
