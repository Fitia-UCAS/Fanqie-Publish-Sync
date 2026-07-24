from __future__ import annotations


import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

DEFAULT_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5")


def ensure_dir(path: str | Path) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def read_text(path: str | Path, encoding: str = "utf-8") -> str:
    return Path(path).read_text(encoding=encoding)


def read_text_auto(path: str | Path, encodings: Iterable[str] = DEFAULT_ENCODINGS) -> str:
    file_path = Path(path)
    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding, newline="") as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    with open(file_path, "r", encoding="gb18030", errors="ignore", newline="") as f:
        return f.read()


def read_text_and_encoding(path: str | Path, encodings: Iterable[str] | None = None) -> tuple[str, str]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"找不到文件：{file_path}")
    raw = file_path.read_bytes()
    candidates = tuple(
        encodings
        or (("utf-8-sig", "utf-8", "gb18030", "gbk") if raw.startswith(b"\xef\xbb\xbf") else ("utf-8", "gb18030", "gbk"))
    )
    for encoding in candidates:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"无法识别文件编码：{file_path}")


def write_text(path: str | Path, text: str, encoding: str = "utf-8", newline: str = "") -> Path:
    return atomic_write_text(path, text, encoding=encoding, newline=newline)


def atomic_write_text(
    path: str | Path,
    text: str,
    *,
    encoding: str = "utf-8",
    newline: str = "",
    backup_path: str | Path | None = None,
) -> Path:
    target = Path(path)
    ensure_dir(target.parent)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            newline=newline,
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary = Path(file.name)
            file.write(text)
            file.flush()
            os.fsync(file.fileno())

        if backup_path is not None and target.is_file():
            backup = Path(backup_path)
            ensure_dir(backup.parent)
            _atomic_copy_file(target, backup)

        os.replace(temporary, target)
        temporary = None
        _fsync_directory(target.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target


def numbered_backup_path(
    source: str | Path,
    backup_dir: str | Path,
    *,
    label: str | None = None,
    suffix: str | None = None,
) -> Path:

    source_path = Path(source)
    target_dir = ensure_dir(backup_dir)
    backup_suffix = suffix if suffix is not None else source_path.suffix
    stem_parts = [source_path.stem]
    if label:
        stem_parts.append(_safe_backup_label(label))
    prefix = "_".join(part for part in stem_parts if part)
    pattern = re.compile(rf"^{re.escape(prefix)}_backup(\d{{3}})_\d{{8}}_\d{{6}}{re.escape(backup_suffix)}$")
    max_index = 0
    for candidate in target_dir.glob(f"{prefix}_backup*{backup_suffix}"):
        match = pattern.match(candidate.name)
        if match:
            max_index = max(max_index, int(match.group(1)))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return target_dir / f"{prefix}_backup{max_index + 1:03d}_{timestamp}{backup_suffix}"


def backup_file(
    source: str | Path,
    backup_dir: str | Path,
    *,
    backup_name: str | None = None,
    cleanup_existing: bool = False,
) -> Path:
    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"未找到文件：{source_path}")
    target_dir = ensure_dir(backup_dir)
    if cleanup_existing:
        for old_file in target_dir.glob(f"{source_path.stem}*{source_path.suffix}"):
            if old_file.is_file():
                old_file.unlink()
    backup_path = target_dir / backup_name if backup_name else numbered_backup_path(source_path, target_dir)
    shutil.copy2(source_path, backup_path)
    _fsync_file(backup_path)
    return backup_path


def _fsync_file(path: Path) -> None:
    with path.open("r+b") as file:
        os.fsync(file.fileno())


def _atomic_copy_file(source: Path, destination: Path) -> None:
    temporary: Path | None = None
    try:
        with source.open("rb") as source_file:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as backup_file:
                temporary = Path(backup_file.name)
                shutil.copyfileobj(source_file, backup_file)
                backup_file.flush()
                os.fsync(backup_file.fileno())
        shutil.copystat(source, temporary)
        os.replace(temporary, destination)
        temporary = None
        _fsync_directory(destination.parent)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _safe_backup_label(label: str) -> str:
    text = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", str(label).strip())
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "backup"
