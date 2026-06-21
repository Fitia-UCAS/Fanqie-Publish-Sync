from __future__ import annotations

import json
from pathlib import Path

from backend.runtime.jobs.events import TaskEvent
from backend.runtime.jobs.results import TaskResult


def test_task_result_result_kind_and_display_name_are_stable() -> None:
    payload = TaskResult(
        True,
        "done",
        path=Path("data/output.txt"),
        result_kind="output_file",
    ).to_dict()

    assert payload["resultKind"] == "output_file"
    assert payload["displayName"] == "output.txt"
    json.dumps(payload, ensure_ascii=False)


def test_task_event_preserves_complete_log_prefix() -> None:
    message = "后台批量处理：第 39 章（9/47）"

    event = TaskEvent.from_log_message("chapter_sync", message)

    assert event.label == "后台批量处理"
    assert event.display_message() == message


def test_task_event_does_not_add_information_label_to_plain_log() -> None:
    message = "正在打开章节编辑页..."

    event = TaskEvent.from_log_message("chapter_sync", message)

    assert event.label == "信息"
    assert event.display_message() == message
