from pathlib import Path

import pytest

from backend.platforms.fanqie.syncing import local_source


def test_replacing_chapter_keeps_backup_and_updates_target_atomically(tmp_path: Path) -> None:
    novel = tmp_path / "novel.txt"
    backup_dir = tmp_path / "backups"
    novel.write_text("第1章 旧标题\n\n旧正文\n\n第2章 后续\n\n后续正文\n", encoding="utf-8")

    backup = local_source.replace_local_chapter_in_single_file(
        novel,
        no=1,
        title="新标题",
        content="新正文",
        backup_dir=backup_dir,
    )

    assert "旧正文" in backup.read_text(encoding="utf-8")
    updated = novel.read_text(encoding="utf-8")
    assert "第1章 新标题" in updated
    assert "新正文" in updated
    assert "第2章 后续" in updated
    assert list(tmp_path.glob(".novel.txt.*.tmp")) == []


def test_backup_failure_leaves_original_novel_untouched(tmp_path: Path, monkeypatch) -> None:
    novel = tmp_path / "novel.txt"
    backup_dir = tmp_path / "backups"
    original = "第1章 原标题\n\n原正文\n"
    novel.write_text(original, encoding="utf-8")

    def fail_write(*args, **kwargs):
        raise OSError("backup failed")

    monkeypatch.setattr(local_source, "write_text", fail_write)

    with pytest.raises(OSError, match="backup failed"):
        local_source.replace_local_chapter_in_single_file(
            novel,
            no=1,
            title="新标题",
            content="新正文",
            backup_dir=backup_dir,
        )

    assert novel.read_text(encoding="utf-8") == original
