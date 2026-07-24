from backend.runtime.jobs.registry import TaskRegistry


def test_shared_resource_blocks_different_tasks_until_owner_finishes() -> None:
    registry = TaskRegistry()

    assert registry.start_task("auto_publish", resource="fanqie_browser")
    assert not registry.start_task("chapter_sync", resource="fanqie_browser")
    assert registry.blocking_task("chapter_sync", resource="fanqie_browser") == "auto_publish"

    registry.finish_task("auto_publish")

    assert registry.start_task("chapter_sync", resource="fanqie_browser")


def test_unrelated_tasks_can_run_while_platform_resource_is_busy() -> None:
    registry = TaskRegistry()

    assert registry.start_task("auto_publish", resource="fanqie_browser")
    assert registry.start_task("novel_processor")
    assert registry.is_running("auto_publish")
    assert registry.is_running("novel_processor")


def test_finishing_non_owner_does_not_release_resource() -> None:
    registry = TaskRegistry()

    assert registry.start_task("auto_publish", resource="fanqie_browser")
    registry.finish_task("chapter_sync")

    assert not registry.start_task("fanqie_login", resource="fanqie_browser")
