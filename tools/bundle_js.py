from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT_DIR / "frontend" / "assets"
BUNDLE_OUT = ASSETS_DIR / "bundle.js"

HEADER = ""

SCRIPTS = [
    "assets/core/page_registry.js",
    "assets/core/form_controls.js",
    "assets/core/state_store.js",
    "assets/core/task_panel.js",
    "assets/pages/fanqie_syncer.js",
    "assets/pages/fanqie_publisher.js",
    "assets/app.js",
]


def bundle() -> None:
    parts: list[str] = [HEADER]
    total_bytes = 0

    for src in SCRIPTS:
        path = ROOT_DIR / "frontend" / src
        if not path.is_file():
            raise SystemExit(f"文件不存在: {path}")

        content = path.read_text(encoding="utf-8")
        total_bytes += len(content.encode("utf-8"))

        parts.append("\n")
        parts.append(content)
        parts.append("\n")

    BUNDLE_OUT.parent.mkdir(parents=True, exist_ok=True)
    BUNDLE_OUT.write_text("".join(parts), encoding="utf-8")
    print(f"✓ {BUNDLE_OUT}")
    print(f"  {len(SCRIPTS)} 个文件 → {total_bytes:,} bytes")


if __name__ == "__main__":
    bundle()
