from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


@dataclass
class TaskRegistry:
    busy_tasks: set[str] = field(default_factory=set)
    task_resources: dict[str, str] = field(default_factory=dict)
    busy_resources: dict[str, str] = field(default_factory=dict)
    stopped_tasks: set[str] = field(default_factory=set)
    paused_tasks: set[str] = field(default_factory=set)
    lock: Lock = field(default_factory=Lock)

    def start_task(self, name: str, *, resource: str | None = None) -> bool:
        normalized_resource = str(resource or "").strip()
        with self.lock:
            if name in self.busy_tasks:
                return False
            if normalized_resource and normalized_resource in self.busy_resources:
                return False
            self.busy_tasks.add(name)
            if normalized_resource:
                self.task_resources[name] = normalized_resource
                self.busy_resources[normalized_resource] = name
            self.stopped_tasks.discard(name)
            self.paused_tasks.discard(name)
            return True

    def finish_task(self, name: str) -> None:
        with self.lock:
            self.busy_tasks.discard(name)
            resource = self.task_resources.pop(name, None)
            if resource and self.busy_resources.get(resource) == name:
                self.busy_resources.pop(resource, None)
            self.stopped_tasks.discard(name)
            self.paused_tasks.discard(name)

    def blocking_task(self, name: str, *, resource: str | None = None) -> str | None:
        normalized_resource = str(resource or "").strip()
        with self.lock:
            if name in self.busy_tasks:
                return name
            return self.busy_resources.get(normalized_resource) if normalized_resource else None

    def request_stop(self, name: str) -> bool:
        with self.lock:
            if name not in self.busy_tasks:
                return False
            self.stopped_tasks.add(name)
            return True


    def request_pause(self, name: str) -> bool:
        with self.lock:
            if name not in self.busy_tasks:
                return False
            self.paused_tasks.add(name)
            return True

    def request_resume(self, name: str) -> bool:
        with self.lock:
            if name not in self.busy_tasks:
                return False
            self.paused_tasks.discard(name)
            return True

    def is_pause_requested(self, name: str) -> bool:
        with self.lock:
            return name in self.paused_tasks

    def is_stop_requested(self, name: str) -> bool:
        with self.lock:
            return name in self.stopped_tasks

    def is_running(self, name: str) -> bool:
        with self.lock:
            return name in self.busy_tasks
