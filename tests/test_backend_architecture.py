from __future__ import annotations

import ast
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"


def _imports() -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    for path in BACKEND_DIR.rglob("*.py"):
        module = ".".join(path.with_suffix("").relative_to(ROOT_DIR).parts)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("backend."):
                edges.append((module, node.module))
            elif isinstance(node, ast.Import):
                edges.extend((module, alias.name) for alias in node.names if alias.name.startswith("backend."))
    return edges


def test_interface_entrypoints_exist() -> None:
    assert (BACKEND_DIR / "interface" / "desktop").is_dir()
    assert (BACKEND_DIR / "interface" / "http").is_dir()
    assert (BACKEND_DIR / "interface" / "cli").is_dir()


def test_features_do_not_depend_on_desktop_interface() -> None:
    for source, target in _imports():
        if source.startswith("backend.features"):
            assert not target.startswith("backend.interface"), f"{source} must not import {target}"


def test_platforms_do_not_depend_on_interface_or_bootstrap() -> None:
    for source, target in _imports():
        if source.startswith("backend.platforms"):
            assert not target.startswith(("backend.interface", "backend.bootstrap")), f"{source} must not import {target}"


def test_runtime_and_infrastructure_do_not_depend_on_features_or_platforms() -> None:
    for source, target in _imports():
        if source.startswith(("backend.runtime", "backend.infrastructure")):
            assert not target.startswith(("backend.features", "backend.platforms", "backend.interface")), f"{source} must not import {target}"


def test_legacy_backend_layers_are_removed() -> None:
    for name in ("adapters", "api", "models", "services", "shared", "task_logs", "workflows"):
        assert not (BACKEND_DIR / name).exists()


def test_production_modules_do_not_import_private_names_across_modules() -> None:
    production_files = [ROOT_DIR / "main.py", *BACKEND_DIR.rglob("*.py")]
    violations: list[str] = []

    for path in production_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            for imported in node.names:
                if imported.name.startswith("_"):
                    violations.append(f"{path.relative_to(ROOT_DIR)} imports {node.module}.{imported.name}")

    assert violations == []
