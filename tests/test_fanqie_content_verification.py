from pathlib import Path
from types import SimpleNamespace

from backend.features.syncing.models import ChapterSyncResult
from backend.platforms.fanqie import content_verification
from backend.platforms.fanqie.syncing import batch, preflight


def _local(body: str = "正文") -> SimpleNamespace:
    return SimpleNamespace(
        subtitle="标题",
        full_title="第1章 标题",
        content=body,
    )


def test_editor_count_is_the_exact_list_refresh_target(monkeypatch) -> None:
    monkeypatch.setattr(
        preflight,
        "build_chapter_row_index",
        lambda *args, **kwargs: {1: {"word_count": 1000, "title": "第1章 标题"}},
    )

    failures = preflight.verify_chapter_list_word_counts(
        object(),
        chapter_manage_url="https://fanqienovel.com/manage",
        local_chapters={1: _local()},
        chapter_numbers=[1],
        expected_counts={1: 1001},
        log=lambda _message: None,
    )

    assert "编辑器字数 1001" in failures[1]


def test_remote_content_match_ignores_list_count_difference(monkeypatch) -> None:
    local = _local("第一段\n\n第二段")
    monkeypatch.setattr(content_verification, "open_chapter_editor", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        content_verification,
        "get_remote_chapter",
        lambda _page: ("标题", "第一段\n第二段", object(), object()),
    )
    monkeypatch.setattr(content_verification, "save_debug", lambda *args, **kwargs: None)

    failure = content_verification.verify_remote_content_matches(
        object(),
        chapter_no=1,
        chapter_manage_url="https://fanqienovel.com/manage",
        local=local,
        log=lambda _message: None,
    )

    assert failure is None


def test_remote_content_mismatch_generates_diff(monkeypatch, tmp_path: Path) -> None:
    diff_path = tmp_path / "diff.patch"
    monkeypatch.setattr(content_verification, "open_chapter_editor", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        content_verification,
        "get_remote_chapter",
        lambda _page: ("旧标题", "旧正文", object(), object()),
    )
    monkeypatch.setattr(content_verification, "save_debug", lambda *args, **kwargs: None)
    monkeypatch.setattr(content_verification, "save_failure_debug", lambda *args, **kwargs: None)
    monkeypatch.setattr(content_verification, "make_git_diff", lambda **kwargs: diff_path)

    failure = content_verification.verify_remote_content_matches(
        object(),
        chapter_no=1,
        chapter_manage_url="https://fanqienovel.com/manage",
        local=_local("新正文"),
        log=lambda _message: None,
    )

    assert failure is not None
    assert "平台最新内容与本地不一致" in failure
    assert str(diff_path) in failure


def test_batch_count_failure_falls_back_to_remote_content(monkeypatch) -> None:
    local = _local()
    result = ChapterSyncResult(
        ok=True,
        changed=True,
        published=True,
        message="submitted",
        platform_editor_count=1001,
    )
    state = batch.MultiChapterSyncState([1], [result], [1])
    captured: dict[str, object] = {}

    monkeypatch.setattr(batch, "_local_chapters_by_number", lambda *args, **kwargs: {1: local})

    def wait_counts(*args, **kwargs):
        captured["expected_counts"] = kwargs.get("expected_counts")
        return {1: "list count differs"}

    monkeypatch.setattr(batch, "wait_for_chapter_list_word_counts", wait_counts)
    monkeypatch.setattr(batch, "verify_remote_content_matches", lambda *args, **kwargs: None)

    batch._final_list_verify_if_needed(
        page=object(),
        options=SimpleNamespace(should_final_list_verify=True),
        chapter_manage_url="https://fanqienovel.com/manage",
        local_chapters={1: local},
        chapters=[1],
        novel_file=Path("novel.txt"),
        state=state,
        log=lambda _message: None,
    )

    assert captured["expected_counts"] == {1: 1001}
    assert result.ok is True
