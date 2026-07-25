from backend.runtime.jobs.callbacks import TaskCallbacks
from backend.runtime.run_logs.fanqie import FanqieTaskLog


def test_task_log_forwards_complete_runtime_output_to_frontend(tmp_path, monkeypatch) -> None:
    received: list[tuple[str, str]] = []
    monkeypatch.setattr(
        FanqieTaskLog,
        "_make_log_path",
        staticmethod(lambda **kwargs: tmp_path / "task.log"),
    )
    task_log = FanqieTaskLog(
        callbacks=TaskCallbacks(log=lambda message, level: received.append((message, level))),
        task_kind="auto_publish",
        operation="publish",
        start=1,
        end=1,
        total=1,
    )

    task_log.emit_start("publish", 1, 1)
    task_log.log("番茄发布调试截图已关闭。")
    task_log.log("本地：第 1 章《测试》")
    task_log.log("失败：第 1 章｜正文编辑器写入失败")
    task_log.finish(0, 1)

    messages = [message for message, level in received]
    assert "任务：番茄发布" in messages
    assert "番茄发布调试截图已关闭。" in messages
    assert "本地：第 1 章《测试》" in messages
    assert "失败：第 1 章｜正文编辑器写入失败" in messages
    assert "任务结束：成功 0/1。" in messages


def test_task_log_localizes_header_and_hides_tracking_noise_from_console(tmp_path, monkeypatch) -> None:
    received: list[tuple[str, str]] = []
    log_path = tmp_path / "task.log"
    monkeypatch.setattr(
        FanqieTaskLog,
        "_make_log_path",
        staticmethod(lambda **kwargs: log_path),
    )
    task_log = FanqieTaskLog(
        callbacks=TaskCallbacks(log=lambda message, level: received.append((message, level))),
        task_kind="chapter_sync",
        operation="publish",
        start=31,
        end=77,
        total=47,
    )

    task_log.log("番茄同步 Git 追踪已开启。")
    task_log.log(r"Diff：E:\data\chapter_039\diff.patch")
    task_log.log("Git：已记录差异提交 f4a3b1d")
    task_log.log(r"Git追踪目录：E:\data\chapter_039\history")

    header_and_details = log_path.read_text(encoding="utf-8")
    assert "任务：番茄同步" in header_and_details
    assert "操作：正式发布" in header_and_details
    assert "范围：第 31 章到第 77 章" in header_and_details
    assert "Diff：" in header_and_details
    assert [message for message, _level in received] == ["番茄同步 Git 追踪已开启。"]


def test_task_log_describes_explicit_chapters_in_processing_order(tmp_path, monkeypatch) -> None:
    received: list[tuple[str, str]] = []
    log_path = tmp_path / "task.log"
    monkeypatch.setattr(
        FanqieTaskLog,
        "_make_log_path",
        staticmethod(lambda **kwargs: log_path),
    )
    chapters = [70, 53, 51, 48, 29, 28]
    task_log = FanqieTaskLog(
        callbacks=TaskCallbacks(log=lambda message, level: received.append((message, level))),
        task_kind="chapter_sync",
        operation="publish",
        start=28,
        end=70,
        total=len(chapters),
        chapters=chapters,
    )

    task_log.emit_start("publish", 28, 70, chapters=chapters)

    assert "章节：70、53、51、48、29、28" in log_path.read_text(encoding="utf-8")
    assert ("章节：70、53、51、48、29、28", "info") in received
