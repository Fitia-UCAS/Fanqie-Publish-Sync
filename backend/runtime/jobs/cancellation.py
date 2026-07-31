from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from backend.runtime.errors import TaskCancelled


StopCallback = Callable[[], bool]


@dataclass(slots=True)
class CancellationGuard:
    """Cooperative cancellation checkpoints for synchronous browser flows."""

    should_stop: StopCallback | None = None

    def requested(self) -> bool:
        return bool(self.should_stop and self.should_stop())

    def checkpoint(self) -> None:
        if self.requested():
            raise TaskCancelled("任务已由用户立即终止。")

    def wait_page(self, page, timeout_ms: int, *, slice_ms: int = 200) -> None:
        remaining = max(0, int(timeout_ms))
        if remaining == 0:
            self.checkpoint()
            return
        if self.should_stop is None:
            page.wait_for_timeout(remaining)
            return
        interval = max(50, int(slice_ms))
        while remaining > 0:
            self.checkpoint()
            current = min(interval, remaining)
            page.wait_for_timeout(current)
            remaining -= current
        self.checkpoint()


__all__ = ["CancellationGuard"]
