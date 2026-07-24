from pathlib import Path

import pytest

from backend.infrastructure.files import storage


def test_atomic_write_preserves_original_when_replace_fails(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "novel.txt"
    target.write_text("旧正文", encoding="utf-8")

    def fail_replace(source: Path, destination: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(storage.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        storage.atomic_write_text(target, "新正文")

    assert target.read_text(encoding="utf-8") == "旧正文"
    assert list(tmp_path.glob(".novel.txt.*.tmp")) == []


def test_atomic_write_keeps_previous_version_as_backup(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    backup = tmp_path / "config.json.bak"
    target.write_text('{"version": 1}', encoding="utf-8")

    storage.atomic_write_text(target, '{"version": 2}', backup_path=backup)

    assert target.read_text(encoding="utf-8") == '{"version": 2}'
    assert backup.read_text(encoding="utf-8") == '{"version": 1}'
