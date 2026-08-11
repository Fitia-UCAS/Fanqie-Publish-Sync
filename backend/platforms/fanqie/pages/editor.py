from __future__ import annotations

from backend.platforms.fanqie.pages.editor_fields import (
    EditorFieldsNotReady,
    EditorWriteNotReady,
    RetryableEditorError,
    all_input_like,
    editor_body_counter_confirms,
    element_text_or_value,
    get_remote_chapter,
    pick_chapter_no_title_and_editor,
    pick_title_and_editor,
    reported_body_word_count,
)
from backend.platforms.fanqie.pages.editor_navigation import (
    ChapterEditorNotFound,
    click_edit_near_chapter_by_js,
    open_chapter_editor,
)
from backend.platforms.fanqie.pages.editor_saving import click_save_draft, wait_for_editor_saved
from backend.platforms.fanqie.pages.editor_writing import fill_locator

__all__ = [
    "ChapterEditorNotFound",
    "EditorFieldsNotReady",
    "EditorWriteNotReady",
    "RetryableEditorError",
    "all_input_like",
    "click_edit_near_chapter_by_js",
    "click_save_draft",
    "editor_body_counter_confirms",
    "element_text_or_value",
    "fill_locator",
    "get_remote_chapter",
    "open_chapter_editor",
    "pick_chapter_no_title_and_editor",
    "pick_title_and_editor",
    "reported_body_word_count",
    "wait_for_editor_saved",
]
