from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BookProfile(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    name: str
    novel_file: str = Field(alias="novelFile")
    chapter_manage_url: str = Field(alias="chapterManageUrl")


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
    browser_headless: bool = Field(default=True, alias="browserHeadless")
    dedupe_debug_screenshots: bool = Field(default=True, alias="dedupeDebugScreenshots")
    git_tracking: bool = Field(default=True, alias="gitTracking")
    operation: str = "publish"
    manual_schedule: bool = Field(default=False, alias="manualSchedule")
    schedule_start_date: str = Field(default="", alias="scheduleStartDate")
    schedule_morning_time: str = Field(default="10:00", alias="scheduleMorningTime")
    schedule_morning_count: int = Field(default=1, ge=0, alias="scheduleMorningCount")
    schedule_afternoon_time: str = Field(default="18:00", alias="scheduleAfternoonTime")
    schedule_afternoon_count: int = Field(default=0, ge=0, alias="scheduleAfternoonCount")
    chapter_selection: str = Field(default="", alias="chapterSelection")
    sync_concurrency: int = Field(default=2, alias="syncConcurrency", ge=1, le=6)
    clear_author_note: bool = Field(default=False, alias="clearAuthorNote")
    book_profile_id: str = Field(default="", alias="bookProfileId")
    expected_book_name: str = Field(default="", alias="expectedBookName")


class AppConfigModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    active_page: str = Field(default="auto_publish", alias="activePage")
    active_book_id: str = Field(default="", alias="activeBookId")
    book_profiles: list[BookProfile] = Field(default_factory=list, alias="bookProfiles")
    auto_publish: TaskSettings = Field(default_factory=TaskSettings)
    chapter_sync: TaskSettings = Field(default_factory=TaskSettings)

    def to_frontend_dict(self) -> dict:
        return self.model_dump(by_alias=True)
