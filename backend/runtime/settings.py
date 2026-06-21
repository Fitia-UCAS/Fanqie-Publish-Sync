from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    browser_channel: str
    webview_storage_dir: Path
    log_level: str

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "RuntimeSettings":
        values = os.environ if environ is None else environ
        storage_override = str(values.get("NOVEL_TOOLS_WEBVIEW_STORAGE_DIR") or "").strip()
        storage_dir = (
            Path(storage_override).expanduser()
            if storage_override
            else user_data_path("FanqiePublishSync", appauthor=False) / "pywebview"
        )
        return cls(
            browser_channel=str(values.get("NOVEL_TOOLS_BROWSER_CHANNEL") or "msedge").strip() or "msedge",
            webview_storage_dir=storage_dir,
            log_level=str(values.get("NOVEL_TOOLS_LOG_LEVEL") or "INFO").strip().upper() or "INFO",
        )
