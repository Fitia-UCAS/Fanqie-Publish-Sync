from __future__ import annotations


from pathlib import Path


def iter_text_files(folder: str | Path) -> list[Path]:
    raw_path = str(folder or "").strip()
    if not raw_path:
        return []
    root = Path(raw_path)
    if not root.exists() or not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*.txt") if path.is_file())


