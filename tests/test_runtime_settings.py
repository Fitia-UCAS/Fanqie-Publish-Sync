from pathlib import Path

from backend.runtime.settings import RuntimeSettings


def test_runtime_settings_use_environment_only_for_runtime_overrides(tmp_path: Path) -> None:
    settings = RuntimeSettings.from_environment(
        {
            "NOVEL_TOOLS_BROWSER_CHANNEL": "chrome",
            "NOVEL_TOOLS_WEBVIEW_STORAGE_DIR": str(tmp_path / "webview"),
            "NOVEL_TOOLS_LOG_LEVEL": "debug",
        }
    )

    assert settings.browser_channel == "chrome"
    assert settings.webview_storage_dir == tmp_path / "webview"
    assert settings.log_level == "DEBUG"
