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
