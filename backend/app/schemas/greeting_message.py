from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


GreetingTone = Literal["concise", "professional", "warm"]


class GreetingCreate(BaseModel):
    job_id: int = Field(gt=0)
    resume_id: int = Field(gt=0)
    tone: GreetingTone = "professional"


class GreetingUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=1_000)

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class GreetingApprove(BaseModel):
    confirmed: bool


class GreetingRead(BaseModel):
    id: int
    job_id: int
    resume_id: int
    match_id: int | None
    job_title: str
    company_name: str
    resume_title: str
    tone: GreetingTone
    content: str
    status: Literal["draft", "approved"]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
