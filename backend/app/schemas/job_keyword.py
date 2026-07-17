from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class JobKeywordCreate(BaseModel):
    keyword: str = Field(min_length=1, max_length=50)
    is_active: bool = True

    @field_validator("keyword", mode="before")
    @classmethod
    def clean_keyword(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class JobKeywordRead(JobKeywordCreate):
    id: int
    created_at: datetime
    updated_at: datetime
