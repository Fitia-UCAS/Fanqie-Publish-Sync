from __future__ import annotations

from datetime import datetime
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from backend.infrastructure.files.storage import write_text
from backend.platforms.fanqie.publishing.local_source import Chapter
from backend.features.novel_processing.text_normalizer import normalize_novel_body
from backend.runtime.paths import PUBLISH_TRACKER_DIR


def track_publish_chapter(chapter_no: int, local: Chapter, *, enabled: bool, log: Callable[[str], None]) -> Path | None:
    if not enabled:
        return None
    directory = _write_publish_snapshot(chapter_no, local)
    commit_id = _commit_publish_snapshot(PUBLISH_TRACKER_DIR, chapter_no)
    log(f"Git：已记录发文章节 {commit_id}" if commit_id else "Git：未检测到 Git 或无需新增提交")
    log(f"Git追踪目录：{directory}")
    return directory


def _write_publish_snapshot(chapter_no: int, local: Chapter) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    directory = PUBLISH_TRACKER_DIR / "chapters" / f"chapter_{chapter_no:03d}" / ts
    directory.mkdir(parents=True, exist_ok=True)
    write_text(
        directory / "local.txt",
        f"标题：{local.subtitle}\n完整标题：{local.full_title}\n\n{normalize_novel_body(local.content)}\n",
    )
    write_text(
        directory / "meta.txt",
        "\n".join([
            f"chapter_no={chapter_no}",
            f"time={datetime.now().isoformat(timespec='seconds')}",
            f"title={local.subtitle}",
            f"full_title={local.full_title}",
            "",
        ]),
    )
    return directory


def _commit_publish_snapshot(repo: Path, chapter_no: int) -> str:
    if shutil.which("git") is None:
        return ""
    repo.mkdir(parents=True, exist_ok=True)
    if not (repo / ".git").exists():
        subprocess.run(["git", "init"], cwd=str(repo), capture_output=True, text=True, encoding="utf-8", errors="replace")
        _run_git(repo, ["config", "user.name", "fanqie_assistant"])
        _run_git(repo, ["config", "user.email", "fanqie_assistant@local"])
        _run_git(repo, ["config", "core.quotepath", "false"])
    _run_git(repo, ["add", "chapters"])
    changed = _run_git(repo, ["diff", "--cached", "--quiet"])
    if changed.returncode != 1:
        return _latest_commit(repo)
    commit = _run_git(repo, ["commit", "-m", f"publish chapter {chapter_no:03d} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
    if commit.returncode != 0:
        return _latest_commit(repo)
    return _latest_commit(repo)


def _run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, encoding="utf-8", errors="replace")


def _latest_commit(repo: Path) -> str:
    result = _run_git(repo, ["rev-parse", "--short", "HEAD"])
    return result.stdout.strip() if result.returncode == 0 else ""
