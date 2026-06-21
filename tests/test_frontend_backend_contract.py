from __future__ import annotations

from backend.interface.desktop.api import WebviewApi


def test_desktop_api_keeps_frontend_contract() -> None:
    required = {
        "get_state",
        "save_config",
        "choose_file",
        "choose_folder",
        "choose_source",
        "choose_login_state",
        "import_login_state",
        "open_path",
        "open_log",
        "open_backup",
        "reset_login",
        "reset_app_data",
        "auto_publish_run",
        "auto_publish_stop",
        "auto_publish_pause",
        "auto_publish_resume",
        "chapter_sync_run",
        "chapter_sync_stop",
        "chapter_sync_pause",
        "chapter_sync_resume",
    }
    missing = sorted(name for name in required if not callable(getattr(WebviewApi, name, None)))
    assert missing == []
