from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ApplicationStatus = Literal[
    "prepared",
    "submitted",
    "screening",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
]


class ApplicationEvent(BaseModel):
    status: ApplicationStatus
    timestamp: datetime
    note: str = ""


class ApplicationCreate(BaseModel):
    job_id: int = Field(gt=0)
    resume_id: int = Field(gt=0)
    greeting_id: int | None = Field(default=None, gt=0)
    channel: str = Field(default="手动记录", max_length=80)
    next_follow_up_at: datetime | None = None
    notes: str = Field(default="", max_length=2_000)

    @field_validator("channel", "notes", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ApplicationUpdate(BaseModel):
    channel: str = Field(default="手动记录", max_length=80)
    next_follow_up_at: datetime | None = None
    notes: str = Field(default="", max_length=2_000)

    @field_validator("channel", "notes", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ApplicationConfirm(BaseModel):
    confirmed: bool


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus
    note: str = Field(default="", max_length=500)

    @field_validator("note", mode="before")
    @classmethod
    def strip_note(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ApplicationRead(BaseModel):
    id: int
    job_id: int
    resume_id: int
    greeting_id: int | None
    job_title: str
    company_name: str
    resume_title: str
    channel: str
    status: ApplicationStatus
    confirmed_by_user: bool
    applied_at: datetime | None
    next_follow_up_at: datetime | None
    notes: str
    status_history: list[ApplicationEvent]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
