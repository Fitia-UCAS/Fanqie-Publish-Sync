import pytest
from pydantic import ValidationError

from backend.features.task_models import PublishTaskPayload, SyncTaskPayload


def test_publish_payload_normalizes_reverse_chapter_range() -> None:
    payload = PublishTaskPayload.model_validate({"novelFile": "novel.txt", "start": 9, "end": 3})

    assert payload.chapter_range == (3, 9)


def test_sync_payload_exposes_validated_direction() -> None:
    payload = SyncTaskPayload.model_validate({"novelFile": "novel.txt", "operation": "pull"})

    assert payload.direction == "remote_to_local"


def test_sync_payload_rejects_unknown_operation() -> None:
    with pytest.raises(ValidationError):
        SyncTaskPayload.model_validate({"novelFile": "novel.txt", "operation": "delete"})


def test_sync_payload_parses_explicit_chapters_in_ascending_order() -> None:
    payload = SyncTaskPayload.model_validate(
        {
            "novelFile": "novel.txt",
            "chapterSelection": "第28章、29，48 51;53；70、28",
        }
    )

    assert payload.chapter_selection == "28,29,48,51,53,70,28"
    assert payload.chapters == [28, 29, 48, 51, 53, 70]
    assert payload.has_explicit_chapters is True


def test_sync_payload_uses_range_when_explicit_chapters_are_empty() -> None:
    payload = SyncTaskPayload.model_validate(
        {"novelFile": "novel.txt", "start": 9, "end": 7, "chapterSelection": ""}
    )

    assert payload.chapters == [7, 8, 9]
    assert payload.has_explicit_chapters is False


def test_sync_payload_rejects_invalid_explicit_chapters() -> None:
    with pytest.raises(ValidationError, match="指定章节格式不正确"):
        SyncTaskPayload.model_validate(
            {"novelFile": "novel.txt", "chapterSelection": "28、第二十九章、48"}
        )


def test_sync_payload_limits_concurrency_to_safe_range() -> None:
    payload = SyncTaskPayload.model_validate({"novelFile": "novel.txt", "syncConcurrency": 6})

    assert payload.sync_concurrency == 6

    with pytest.raises(ValidationError):
        SyncTaskPayload.model_validate({"novelFile": "novel.txt", "syncConcurrency": 7})


def test_sync_payload_explicit_chapters_take_priority_over_range() -> None:
    payload = SyncTaskPayload.model_validate(
        {"novelFile": "novel.txt", "start": 1, "end": 86, "chapterSelection": "28、53"}
    )

    assert payload.chapters == [28, 53]


@pytest.mark.parametrize("payload_type", [PublishTaskPayload, SyncTaskPayload])
def test_task_payload_controls_browser_visibility(payload_type) -> None:
    assert payload_type.model_validate({"novelFile": "novel.txt"}).browser_headless is True
    assert (
        payload_type.model_validate(
            {"novelFile": "novel.txt", "browserHeadless": False}
        ).browser_headless
        is False
    )


def test_publish_payload_can_clear_independent_author_note_field() -> None:
    payload = PublishTaskPayload.model_validate(
        {"novelFile": "novel.txt", "clearAuthorNote": True}
    )

    assert payload.clear_author_note is True
