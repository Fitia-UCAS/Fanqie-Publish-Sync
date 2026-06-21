from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TaskSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    novel_file: str = Field(default="", alias="novelFile")
    chapter_manage_url: str = Field(default="", alias="chapterManageUrl")
    start: int = Field(default=1, ge=1)
    end: int = Field(default=1, ge=1)
    use_ai: bool = Field(default=False, alias="useAi")
    verify_after_publish: bool = Field(default=True, alias="verifyAfterPublish")
    debug_screenshots: bool = Field(default=True, alias="debugScreenshots")
    failure_screenshots: bool = Field(default=True, alias="failureScreenshots")
    dedupe_debug_screenshots: bool = Field(default=True, alias="dedupeDebugScreenshots")
    git_tracking: bool = Field(default=True, alias="gitTracking")
    operation: str = "publish"
    manual_schedule: bool = Field(default=False, alias="manualSchedule")
    schedule_start_date: str = Field(default="", alias="scheduleStartDate")
    schedule_morning_time: str = Field(default="10:00", alias="scheduleMorningTime")
    schedule_morning_count: int = Field(default=1, ge=0, alias="scheduleMorningCount")
    schedule_afternoon_time: str = Field(default="18:00", alias="scheduleAfternoonTime")
    schedule_afternoon_count: int = Field(default=0, ge=0, alias="scheduleAfternoonCount")


class AppConfigModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    active_page: str = Field(default="auto_publish", alias="activePage")
    auto_publish: TaskSettings = Field(default_factory=TaskSettings)
    chapter_sync: TaskSettings = Field(default_factory=TaskSettings)

    def to_frontend_dict(self) -> dict:
        return self.model_dump(by_alias=True)
