from pathlib import Path

from backend.infrastructure.persistence.config import ConfigRepository


def test_config_repository_preserves_typed_schedule_settings(tmp_path: Path) -> None:
    repository = ConfigRepository(tmp_path / "config.json")
    repository.save(
        {
            "activePage": "auto_publish",
            "auto_publish": {
                "novelFile": "novel.txt",
                "manualSchedule": True,
                "scheduleStartDate": "2026-07-26",
                "scheduleMorningCount": 2,
                "scheduleAfternoonCount": 1,
            },
        }
    )

    config = repository.load()

    assert config["auto_publish"]["novelFile"] == "novel.txt"
    assert config["auto_publish"]["manualSchedule"] is True
    assert config["auto_publish"]["scheduleStartDate"] == "2026-07-26"
    assert config["auto_publish"]["scheduleMorningCount"] == 2
    assert config["auto_publish"]["scheduleAfternoonCount"] == 1


def test_config_repository_migrates_legacy_sections_and_removes_unknown_keys(tmp_path: Path) -> None:
    repository = ConfigRepository(tmp_path / "config.json")

    config = repository.normalize(
        {
            "activePage": "auto_publish_chapters",
            "auto_publish_chapters": {"novelFile": "legacy.txt", "unknown": "ignored"},
            "unknownRoot": True,
        }
    )

    assert config["activePage"] == "auto_publish"
    assert config["auto_publish"]["novelFile"] == "legacy.txt"
    assert "unknown" not in config["auto_publish"]
    assert "unknownRoot" not in config


def test_config_repository_recovers_corrupted_config_from_backup(tmp_path: Path) -> None:
    repository = ConfigRepository(tmp_path / "config.json")
    repository.save({"auto_publish": {"novelFile": "stable.txt"}})
    repository.save({"auto_publish": {"novelFile": "newer.txt"}})
    repository.path.write_text("{broken", encoding="utf-8")

    config = repository.load()

    assert config["auto_publish"]["novelFile"] == "stable.txt"
    assert repository.load()["auto_publish"]["novelFile"] == "stable.txt"
