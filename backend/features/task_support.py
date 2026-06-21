from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from backend.features.novel_processing.chapter_parser import split_chapter_source_paths


def resolve_chapter_source(value: str) -> Path | str:
    raw = str(value or "").strip()
    if not raw:
        raise RuntimeError("请先选择小说文件或章节文件夹。")
    paths = split_chapter_source_paths(raw)
    if not paths:
        raise RuntimeError("请先选择小说文件或章节文件夹。")
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise RuntimeError(f"请选择存在的小说文件或章节文件夹：{missing[0]}")
    return paths[0] if len(paths) == 1 else "\n".join(str(path) for path in paths)


def result_to_dict(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        data = asdict(value)
    elif hasattr(value, "__dict__"):
        data = dict(value.__dict__)
    else:
        return {"message": str(value)}
    return {key: str(item) if isinstance(item, Path) else item for key, item in data.items()}
