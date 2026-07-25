from pathlib import Path
import shutil
import subprocess

import pytest

from backend.features.novel_processing.chapter_parser import parse_chapter_blocks
from backend.platforms.fanqie.history import diff_report
from backend.platforms.fanqie.history import tracker as sync_tracker
from backend.platforms.fanqie.publishing import tracker as publish_tracker

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="Git is not installed")


def test_sync_tracker_commits_changes_and_skips_identical_snapshot(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "sync-history"
    monkeypatch.setattr(sync_tracker, "CHAPTER_SYNC_HISTORY_DIR", repo)
    monkeypatch.setattr(sync_tracker.time, "strftime", lambda _format: "2026-07-25 12:00:00")

    first_changed, _, first_commit = sync_tracker.track_snapshot(1, "本地", "正文", "远端", "正文")
    second_changed, _, second_commit = sync_tracker.track_snapshot(1, "本地", "正文", "远端", "正文")
    third_changed, _, third_commit = sync_tracker.track_snapshot(1, "本地", "正文", "远端", "新正文")

    assert first_changed is True
    assert second_changed is False
    assert third_changed is True
    assert first_commit == second_commit
    assert third_commit != first_commit


def test_publish_tracker_creates_snapshot_and_git_commit(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "publish-history"
    monkeypatch.setattr(publish_tracker, "PUBLISH_TRACKER_DIR", repo)
    chapter = parse_chapter_blocks("第3章 测试标题\n\n测试正文")[0]
    logs: list[str] = []

    snapshot = publish_tracker.track_publish_chapter(3, chapter, enabled=True, log=logs.append)

    count = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert snapshot is not None
    assert (snapshot / "local.txt").is_file()
    assert count == "1"
    assert any("Git：已记录发文章节" in message for message in logs)


def test_diff_report_uses_relative_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(diff_report, "CHAPTER_SYNC_COMPARE_DIR", tmp_path)

    diff_path = diff_report.make_git_diff(
        chapter_no=70,
        local_title="本地",
        local_body="本地正文",
        remote_title="远端",
        remote_body="远端正文",
    )
    diff_text = diff_path.read_text(encoding="utf-8")

    assert str(tmp_path) not in diff_text
    assert "chapter_070" in diff_text
