from __future__ import annotations


from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "config.json"
DATA_DIR = ROOT_DIR / "data"
LEGACY_COMMON_DIR = DATA_DIR / "common"
LEGACY_CONFIG_FILE = LEGACY_COMMON_DIR / "config.json"


APP_SYSTEM_DIR = DATA_DIR / "app_system"
SYSTEM_TASK_LOG_DIR = APP_SYSTEM_DIR / "app_system_tasklogs"
LOG_NAME = "task.log"
LATEST_LOG_NAME = "latest_task.log"
LOG_FILE = SYSTEM_TASK_LOG_DIR / LATEST_LOG_NAME

PUBLISH_DIR = DATA_DIR / "fanqie_publisher"
PUBLISH_DEBUG_DIR = PUBLISH_DIR / "fanqie_publish_debug"
PUBLISH_TRACKER_DIR = PUBLISH_DIR / "fanqie_publish_tracker"
AUTO_PUBLISH_LOG_DIR = PUBLISH_DIR / "fanqie_publish_tasklogs"

CHAPTER_SYNC_DIR = DATA_DIR / "fanqie_syncer"
CHAPTER_SYNC_BACKUP_DIR = CHAPTER_SYNC_DIR / "fanqie_sync_backups"
CHAPTER_SYNC_COMPARE_DIR = CHAPTER_SYNC_DIR / "fanqie_sync_compare_reports"
CHAPTER_SYNC_DEBUG_DIR = CHAPTER_SYNC_DIR / "fanqie_sync_debug"
CHAPTER_SYNC_HISTORY_DIR = CHAPTER_SYNC_DIR / "fanqie_sync_history"
CHAPTER_SYNC_LOG_DIR = CHAPTER_SYNC_DIR / "fanqie_sync_tasklogs"

BROWSER_DATA_DIR = DATA_DIR / "fanqie_web"
FANQIE_AUTH_STATE_FILE = BROWSER_DATA_DIR / "state.json"
FANQIE_ACCOUNTS_FILE = BROWSER_DATA_DIR / "accounts.json"
FANQIE_ACCOUNT_STATES_DIR = BROWSER_DATA_DIR / "states"

PROJECT_DIRECTORIES: tuple[Path, ...] = (
    CONFIG_DIR,
    DATA_DIR,
    APP_SYSTEM_DIR,
    SYSTEM_TASK_LOG_DIR,
    PUBLISH_DIR,
    PUBLISH_DEBUG_DIR,
    PUBLISH_TRACKER_DIR,
    AUTO_PUBLISH_LOG_DIR,
    CHAPTER_SYNC_DIR,
    CHAPTER_SYNC_BACKUP_DIR,
    CHAPTER_SYNC_COMPARE_DIR,
    CHAPTER_SYNC_DEBUG_DIR,
    CHAPTER_SYNC_HISTORY_DIR,
    CHAPTER_SYNC_LOG_DIR,
    BROWSER_DATA_DIR,
)

LOG_CATEGORIES: dict[str, Path] = {
    "system": SYSTEM_TASK_LOG_DIR,
    "auto_publish": AUTO_PUBLISH_LOG_DIR,
    "chapter_sync": CHAPTER_SYNC_LOG_DIR,
}


def ensure_data_directories() -> None:
    for directory in PROJECT_DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)


def task_log_file(category: str) -> Path:
    directory = LOG_CATEGORIES.get(category, SYSTEM_TASK_LOG_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return directory / f"task_{stamp}.log"


def latest_log_file(category: str) -> Path:
    directory = LOG_CATEGORIES.get(category, SYSTEM_TASK_LOG_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    logs = sorted(directory.glob("task_*.log"), key=_path_mtime, reverse=True)
    return logs[0] if logs else directory / LATEST_LOG_NAME


def get_state_paths() -> dict[str, str]:
    return {
        "config": str(CONFIG_DIR),
        "config_file": str(CONFIG_FILE),
        "data": str(DATA_DIR),
        "task_logs": str(DATA_DIR),
        "fanqie_publisher": str(PUBLISH_DIR),
        "fanqie_syncer": str(CHAPTER_SYNC_DIR),
        "system_logs": str(SYSTEM_TASK_LOG_DIR),
        "auto_publish_logs": str(AUTO_PUBLISH_LOG_DIR),
        "publisher_debug": str(PUBLISH_DEBUG_DIR),
        "publisher_tracker": str(PUBLISH_TRACKER_DIR),
        "chapter_sync_logs": str(CHAPTER_SYNC_LOG_DIR),
        "fanqie_sync_tasklogs": str(CHAPTER_SYNC_LOG_DIR),
        "chapter_sync_backups": str(CHAPTER_SYNC_BACKUP_DIR),
        "chapter_sync_compare": str(CHAPTER_SYNC_COMPARE_DIR),
        "chapter_sync_history": str(CHAPTER_SYNC_HISTORY_DIR),
        "chapter_sync_debug": str(CHAPTER_SYNC_DEBUG_DIR),
        "debug": str(CHAPTER_SYNC_DEBUG_DIR),
        "fanqie_auth_state": str(FANQIE_AUTH_STATE_FILE),
        "fanqie_accounts_file": str(FANQIE_ACCOUNTS_FILE),
        "fanqie_account_states": str(FANQIE_ACCOUNT_STATES_DIR),
    }




def _path_mtime(path: Path) -> float:
    return path.stat().st_mtime
