from __future__ import annotations

from pathlib import Path

from backend.platforms.fanqie.actions import interactions


class FakePage:
    def __init__(self) -> None:
        self.url = "https://passport.example/login"
        self.closed = False
        self.waits = 0

    def is_closed(self) -> bool:
        return self.closed

    def wait_for_timeout(self, value: int) -> None:
        self.waits += 1
        if self.waits == 2:
            self.url = "https://fanqienovel.com/writer/zone"


def test_login_waits_for_success_without_default_thirty_second_event(monkeypatch) -> None:
    page = FakePage()
    navigated: list[str] = []
    monkeypatch.setattr(interactions, "page_text", lambda current: "登录" if "passport" in current.url else "作品 章节")
    monkeypatch.setattr(interactions, "goto_chapter_manage", lambda current, url: navigated.append(url))
    interactions.ensure_logged_in(page, "https://fanqienovel.com/manage", timeout_ms=5000, wait_for_login=True)
    assert navigated == ["https://fanqienovel.com/manage"]


def test_http_and_cli_entrypoints_are_reserved() -> None:
    root = Path(__file__).resolve().parents[1] / "backend" / "interface"
    assert (root / "http" / ".gitkeep").exists()
    assert (root / "cli" / ".gitkeep").exists()
