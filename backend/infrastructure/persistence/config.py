from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.infrastructure.files.storage import atomic_write_text
from backend.infrastructure.persistence.config_models import AppConfigModel, TaskSettings
from backend.runtime.paths import CONFIG_FILE, LEGACY_CONFIG_FILE

LEGACY_CONFIG_SECTIONS: dict[str, str] = {
    "auto_publish_chapters": "auto_publish",
    "sync_publish_chapters": "chapter_sync",
}

DEFAULT_CONFIG: dict[str, Any] = AppConfigModel().to_frontend_dict()


@dataclass(frozen=True, slots=True)
class ConfigRepository:
    path: Path
    legacy_path: Path | None = None

    def load(self) -> dict[str, Any]:
        data = self._read_json(self.path)
        restored_from_backup = False
        if not data:
            backup_data = self._read_json(self.backup_path)
            if backup_data:
                data = backup_data
                restored_from_backup = True
        if not data and self.legacy_path and self.legacy_path.exists():
            data = self._read_json(self.legacy_path)
        config = self.normalize(data)
        if not self.path.exists() or restored_from_backup:
            self._write(config, create_backup=False)
        return config

    def save(self, config: dict[str, Any]) -> None:
        normalized = self.normalize(config)
        self._write(normalized, create_backup=True)

    @property
    def backup_path(self) -> Path:
        return self.path.with_name(f"{self.path.name}.bak")

    def _write(self, normalized: dict[str, Any], *, create_backup: bool) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.path,
            json.dumps(normalized, ensure_ascii=False, indent=2),
            backup_path=self.backup_path if create_backup else None,
        )

    def normalize(self, data: dict[str, Any]) -> dict[str, Any]:
        migrated = self._migrate_legacy_sections(data if isinstance(data, dict) else {})
        model = AppConfigModel(
            activePage=str(migrated.get("activePage") or "auto_publish"),
            activeBookId=str(migrated.get("activeBookId") or ""),
            bookProfiles=migrated.get("bookProfiles") if isinstance(migrated.get("bookProfiles"), list) else [],
            auto_publish=self._task_settings(migrated.get("auto_publish")),
            chapter_sync=self._task_settings(migrated.get("chapter_sync")),
        )
        return model.to_frontend_dict()

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _task_settings(value: Any) -> TaskSettings:
        try:
            return TaskSettings.model_validate(value if isinstance(value, dict) else {})
        except ValidationError:
            return TaskSettings()

    @staticmethod
    def _migrate_legacy_sections(data: dict[str, Any]) -> dict[str, Any]:
        migrated = deepcopy(data)
        active_page = migrated.get("activePage")
        if isinstance(active_page, str):
            migrated["activePage"] = LEGACY_CONFIG_SECTIONS.get(active_page, active_page)
        for legacy_key, new_key in LEGACY_CONFIG_SECTIONS.items():
            legacy_value = migrated.pop(legacy_key, None)
            if legacy_value is not None and new_key not in migrated:
                migrated[new_key] = legacy_value
        return migrated


DEFAULT_REPOSITORY = ConfigRepository(CONFIG_FILE, LEGACY_CONFIG_FILE)


def load_config() -> dict[str, Any]:
    return DEFAULT_REPOSITORY.load()


def save_config(config: dict[str, Any]) -> None:
    DEFAULT_REPOSITORY.save(config)


def deep_update(target: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_update(target[key], value)
        else:
            target[key] = value
    return target


def set_config_path(config: dict[str, Any], dotted_path: str, value: Any) -> None:
    if not dotted_path:
        return
    parts = [part for part in dotted_path.split(".") if part]
    current = config
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    if parts:
        current[parts[-1]] = value


def get_config_section(config: dict[str, Any], section: str) -> dict[str, Any]:
    value = config.get(section)
    if not isinstance(value, dict):
        value = {}
        config[section] = value
    return value
