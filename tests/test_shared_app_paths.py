from __future__ import annotations

from backend.runtime.paths import (
    CHAPTER_SYNC_DIR,
    CHAPTER_SYNC_LOG_DIR,
    CONFIG_DIR,
    CONFIG_FILE,
    LOG_CATEGORIES,
    PUBLISH_DIR,
    ROOT_DIR,
    get_state_paths,
    latest_log_file,
    task_log_file,
)


def test_config_file_stays_in_project_config_dir() -> None:
    assert CONFIG_DIR == ROOT_DIR / "config"
    assert CONFIG_FILE == CONFIG_DIR / "config.json"


def test_log_categories_use_timestamped_log_files() -> None:
    for category in LOG_CATEGORIES:
        path = task_log_file(category)
        assert path.name.startswith("task_")
        assert path.name.endswith(".log")
        assert path.parent.name.endswith("_tasklogs")


def test_latest_log_file_uses_stable_fallback() -> None:
    for category in LOG_CATEGORIES:
        path = latest_log_file(category)
        assert path.name.endswith(".log")
        assert path.parent.name.endswith("_tasklogs")


def test_backend_uses_new_architecture_roots() -> None:
    expected = {"bootstrap", "features", "infrastructure", "interface", "platforms", "runtime"}
    actual = {path.name for path in (ROOT_DIR / "backend").iterdir() if path.is_dir() and not path.name.startswith("__")}
    assert expected <= actual


def test_open_directory_aliases_stay_inside_feature_data_dirs() -> None:
    paths = get_state_paths()
    assert paths["fanqie_publisher"] == str(PUBLISH_DIR)
    assert paths["fanqie_syncer"] == str(CHAPTER_SYNC_DIR)
    assert paths["fanqie_sync_tasklogs"] == str(CHAPTER_SYNC_LOG_DIR)
