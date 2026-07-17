from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ResumeBase(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    target_role: str = Field(default="", max_length=120)
    version: int = Field(default=1, ge=1, le=100)
    status: Literal["draft", "ready"] = "draft"
    content: str = Field(default="", max_length=50_000)
    notes: str = Field(default="", max_length=2_000)
    is_primary: bool = False

    @field_validator("title", "target_role", "content", "notes", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        if not value:
            raise ValueError("title cannot be empty")
        return value


class ResumeCreate(ResumeBase):
    pass


class ResumeUpdate(ResumeBase):
    pass


class ResumeRead(ResumeBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
