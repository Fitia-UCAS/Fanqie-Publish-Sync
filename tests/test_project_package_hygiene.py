from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


def test_no_empty_frontend_placeholder_components() -> None:
    assert not (ROOT_DIR / "frontend" / "assets" / "components").exists()


def test_file_helpers_are_grouped_in_infrastructure() -> None:
    files_dir = ROOT_DIR / "backend" / "infrastructure" / "files"
    assert (files_dir / "storage.py").exists()
    assert (files_dir / "discovery.py").exists()
