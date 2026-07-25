from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    chapter_selection: str = Field(default="", alias="chapterSelection")

    @field_validator("chapter_selection")
    @classmethod
    def validate_chapter_selection(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        tokens = [token for token in re.split(r"[,，、;；\s]+", text) if token]
        numbers: list[int] = []
        for token in tokens:
            match = re.fullmatch(r"(?:第)?(\d+)(?:章)?", token)
            if not match or int(match.group(1)) < 1:
                raise ValueError("指定章节格式不正确，请使用类似“28、29、48”的正整数列表。")
            numbers.append(int(match.group(1)))
        return ",".join(str(number) for number in numbers)

    @property
    def direction(self) -> Literal["local_to_remote", "remote_to_local"]:
        return "remote_to_local" if self.operation == "pull" else "local_to_remote"

    @property
    def chapters(self) -> list[int]:
        if not self.chapter_selection:
            start, end = self.chapter_range
            return list(range(start, end + 1))
        selected = {int(value) for value in self.chapter_selection.split(",")}
        return sorted(selected)

    @property
    def has_explicit_chapters(self) -> bool:
        return bool(self.chapter_selection)
