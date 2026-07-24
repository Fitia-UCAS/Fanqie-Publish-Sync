import pytest

from backend.platforms.fanqie.dialogs import publishing_schedule


class FakePage:
    def __init__(self) -> None:
        self.waits: list[int] = []

    def wait_for_timeout(self, timeout: int) -> None:
        self.waits.append(timeout)


def test_automatic_schedule_coordinates_switch_date_and_time(monkeypatch) -> None:
    page = FakePage()
    logs: list[str] = []
    monkeypatch.setattr(publishing_schedule, "save_debug", lambda *args, **kwargs: None)
    monkeypatch.setattr(publishing_schedule, "ensure_scheduled_publish_switch_on", lambda page: True)
    monkeypatch.setattr(
        publishing_schedule,
        "set_automatic_scheduled_publish_date",
        lambda page, date_increment_days: "2026-07-28",
    )
    monkeypatch.setattr(
        publishing_schedule,
        "set_scheduled_publish_time",
        lambda page, scheduled_time: scheduled_time == "10:00",
    )

    result = publishing_schedule.ensure_scheduled_publish_at_10(
        page,
        date_increment_days=3,
        log=logs.append,
    )

    assert result == "2026-07-28"
    assert page.waits == [600, 400]
    assert "2026-07-28" in logs[0]
    assert "10:00" in logs[0]


def test_manual_schedule_stops_when_time_control_is_missing(monkeypatch) -> None:
    page = FakePage()
    monkeypatch.setattr(publishing_schedule, "save_debug", lambda *args, **kwargs: None)
    monkeypatch.setattr(publishing_schedule, "ensure_scheduled_publish_switch_on", lambda page: True)
    monkeypatch.setattr(
        publishing_schedule,
        "set_manual_scheduled_publish_date",
        lambda page, scheduled_date: True,
    )
    monkeypatch.setattr(
        publishing_schedule,
        "set_scheduled_publish_time",
        lambda page, scheduled_time: False,
    )

    with pytest.raises(RuntimeError, match="时间输入框"):
        publishing_schedule.ensure_scheduled_publish(
            page,
            scheduled_date="2026-07-28",
            scheduled_time="18:30",
        )
