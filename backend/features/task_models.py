from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChapterTaskPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    novel_file: str = Field(alias="novelFile")
    chapter_manage_url: str = Field(default="", alias="chapterManageUrl")
    start: int = Field(default=1, ge=1)
    end: int = Field(default=1, ge=1)
    use_ai: bool = Field(default=False, alias="useAi")
    verify_after_publish: bool = Field(default=True, alias="verifyAfterPublish")
    debug_screenshots: bool = Field(default=True, alias="debugScreenshots")
    failure_screenshots: bool = Field(default=True, alias="failureScreenshots")
    git_tracking: bool = Field(default=True, alias="gitTracking")
    auth_state_path: str = Field(default="", alias="authStatePath")
    manual_schedule: bool = Field(default=False, alias="manualSchedule")
    schedule_start_date: str = Field(default="", alias="scheduleStartDate")
    schedule_morning_time: str = Field(default="10:00", alias="scheduleMorningTime")
    schedule_morning_count: int = Field(default=1, ge=0, alias="scheduleMorningCount")
    schedule_afternoon_time: str = Field(default="18:00", alias="scheduleAfternoonTime")
    schedule_afternoon_count: int = Field(default=0, ge=0, alias="scheduleAfternoonCount")

    @property
    def chapter_range(self) -> tuple[int, int]:
        return (self.end, self.start) if self.end < self.start else (self.start, self.end)


class PublishTaskPayload(ChapterTaskPayload):
    operation: Literal["publish"] = "publish"


class SyncTaskPayload(ChapterTaskPayload):
    operation: Literal["publish", "pull"] = "publish"
    task_kind: str = Field(default="chapter_sync", alias="taskKind")

    @property
    def direction(self) -> Literal["local_to_remote", "remote_to_local"]:
        return "remote_to_local" if self.operation == "pull" else "local_to_remote"
