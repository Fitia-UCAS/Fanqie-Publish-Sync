from __future__ import annotations

from playwright.sync_api import Page

from backend.platforms.fanqie.models import ScheduledPublishSlot
from backend.platforms.fanqie.submission import SubmissionFlow, SubmissionMode


def click_next_step(page: Page, log=print) -> None:
    SubmissionFlow(page=page, mode=SubmissionMode.PUBLISH, log=log).enter_settings()


def publish_after_save(
    page: Page,
    use_ai: bool = False,
    log=print,
    scheduled_slot: ScheduledPublishSlot | None = None,
) -> None:
    SubmissionFlow(
        page=page,
        mode=SubmissionMode.PUBLISH,
        use_ai=use_ai,
        log=log,
        scheduled_slot=scheduled_slot,
    ).run()
