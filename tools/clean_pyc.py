from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
CACHE_DIRS = {"__pycache__"}
CACHE_SUFFIXES = {".pyc", ".pyo"}


def collect_cache_paths(root: Path) -> list[Path]:
    paths: list[Path] = []

    for entry in root.rglob("*"):
        if entry.is_dir() and entry.name in CACHE_DIRS:
            paths.append(entry)
        elif entry.is_file() and entry.suffix in CACHE_SUFFIXES:
            paths.append(entry)

    return paths


def remove_cache_paths(paths: list[Path], dry_run: bool) -> int:
    removed = 0

    for path in sorted(paths):
        if dry_run:
            label = "目录" if path.is_dir() else "文件"
            print(f"[DRY-RUN] 将删除 {label}: {path}")
            removed += 1
            continue

        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)

        print(f"已删除: {path}")
        removed += 1

    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description="清除所有 __pycache__ 目录和 .pyc/.pyo 字节码文件")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览将要删除的文件，不实际删除",
    )
    args = parser.parse_args()

    cache_paths = collect_cache_paths(ROOT_DIR)

    if not cache_paths:
        print("没有找到需要清理的缓存文件。")
        return

    removed = remove_cache_paths(cache_paths, dry_run=args.dry_run)
    label = "预览" if args.dry_run else "清理"
    print(f"\n{label}完成，共 {removed} 项。")


if __name__ == "__main__":
    main()
