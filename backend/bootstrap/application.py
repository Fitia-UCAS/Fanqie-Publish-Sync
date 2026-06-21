from __future__ import annotations

from dataclasses import dataclass

from backend.features.publishing.use_cases import PublishChapters
from backend.features.syncing.use_cases import SyncChapters


@dataclass(slots=True)
class ApplicationServices:
    publishing: PublishChapters
    syncing: SyncChapters


def create_application_services() -> ApplicationServices:
    return ApplicationServices(
        publishing=PublishChapters(),
        syncing=SyncChapters(),
    )
