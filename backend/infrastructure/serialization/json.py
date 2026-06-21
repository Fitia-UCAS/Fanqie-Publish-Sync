from __future__ import annotations


from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


def to_json_safe(value: Any) -> JsonValue:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return to_json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): to_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_json_safe(item) for item in value]
    return str(value)


