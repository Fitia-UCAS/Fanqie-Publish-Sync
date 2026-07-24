from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib


ROOT_DIR = Path(__file__).resolve().parents[1]


def _load_pyproject() -> dict[str, Any]:
    with (ROOT_DIR / "pyproject.toml").open("rb") as file:
        return tomllib.load(file)


def _read_requirements(filename: str) -> tuple[list[str], list[str]]:
    requirements: list[str] = []
    includes: list[str] = []
    for raw_line in (ROOT_DIR / filename).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r "):
            includes.append(line.removeprefix("-r ").strip())
        else:
            requirements.append(line)
    return requirements, includes


def _dependency_names(requirements: list[str]) -> set[str]:
    return {
        re.split(r"[\s<>=!~;\[]", requirement, maxsplit=1)[0].lower().replace("_", "-")
        for requirement in requirements
    }


def test_dependency_groups_match_requirements_files() -> None:
    pyproject = _load_pyproject()
    runtime = pyproject["project"]["dependencies"]
    optional = pyproject["project"]["optional-dependencies"]

    runtime_requirements, runtime_includes = _read_requirements("requirements.txt")
    dev_requirements, dev_includes = _read_requirements("requirements-dev.txt")
    build_requirements, build_includes = _read_requirements("requirements-build.txt")

    assert runtime_includes == []
    assert _dependency_names(runtime_requirements) == _dependency_names(runtime)
    assert dev_includes == ["requirements.txt"]
    assert _dependency_names(dev_requirements) == _dependency_names(optional["dev"])
    assert build_includes == ["requirements.txt"]
    assert _dependency_names(build_requirements) == _dependency_names(optional["build"])


def test_tooling_does_not_leak_into_runtime_dependencies() -> None:
    pyproject = _load_pyproject()
    runtime_names = _dependency_names(pyproject["project"]["dependencies"])
    optional = pyproject["project"]["optional-dependencies"]

    assert runtime_names.isdisjoint({"pytest", "ruff", "tomli", "pyinstaller"})
    assert {"pytest", "ruff"}.issubset(_dependency_names(optional["dev"]))
    assert _dependency_names(optional["build"]) == {"pyinstaller"}


def test_build_script_installs_build_requirements() -> None:
    build_script = (ROOT_DIR / "tools" / "build_exe.py").read_text(encoding="utf-8")

    assert 'ROOT_DIR / "requirements-build.txt"' in build_script
