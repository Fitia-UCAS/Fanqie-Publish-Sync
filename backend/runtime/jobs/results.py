from __future__ import annotations


from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from backend.infrastructure.serialization.json import JsonValue, to_json_safe

ResultKind = Literal["message", "output_file", "output_dir", "in_place", "in_place_batch"]


@dataclass(slots=True)
class TaskResult:
    ok: bool
    message: str
    path: Path | None = None
    result_kind: ResultKind = "message"
    display_name: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    error_type: str = ""

    def to_dict(self) -> dict[str, JsonValue]:
        payload: dict[str, Any] = {
            "ok": self.ok,
            "message": self.message,
            "resultKind": self.result_kind,
        }
        if self.path is not None:
            payload["path"] = str(self.path)
            payload["displayName"] = self.display_name or self.path.name
        elif self.display_name:
            payload["displayName"] = self.display_name
        if self.error_type:
            payload["errorType"] = self.error_type
        payload.update(self.data)
        return to_json_safe(payload)

