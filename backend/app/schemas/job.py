from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class JobBase(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    company_name: str = Field(default="", max_length=160)
    city: str = Field(default="", max_length=80)
    salary_min: int | None = Field(default=None, ge=0, le=1_000_000)
    salary_max: int | None = Field(default=None, ge=0, le=1_000_000)
    degree_required: str = Field(default="", max_length=40)
    experience_required: str = Field(default="", max_length=80)
    company_size: str = Field(default="", max_length=40)
    description: str = Field(default="", max_length=20_000)
    source_platform: str = Field(default="manual", max_length=80)
    source_url: str = Field(default="", max_length=500)
    status: Literal["open", "closed"] = "open"
    is_favorite: bool = False

    @field_validator(
        "title",
        "company_name",
        "city",
        "degree_required",
        "experience_required",
        "company_size",
        "description",
        "source_platform",
        "source_url",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        if not value:
            raise ValueError("title cannot be empty")
        return value

    @model_validator(mode="after")
    def validate_salary_range(self) -> "JobBase":
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min cannot exceed salary_max")
        return self


class JobCreate(JobBase):
    pass


class JobUpdate(JobBase):
    pass


class JobRead(JobBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobBulkDeleteRequest(BaseModel):
    job_ids: list[int] = Field(default_factory=list, max_length=500)
    delete_all_imported: bool = False
    preview: bool = False

    @field_validator("job_ids")
    @classmethod
    def normalize_job_ids(cls, values: list[int]) -> list[int]:
        if any(value <= 0 for value in values):
            raise ValueError("job_ids must contain positive integers")
        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def validate_delete_scope(self) -> "JobBulkDeleteRequest":
        if self.delete_all_imported == bool(self.job_ids):
            raise ValueError("choose job_ids or delete_all_imported")
        return self


class JobBulkDeleteRead(BaseModel):
    matched_count: int
    cleared_count: int
    cleared_job_ids: list[int] = Field(default_factory=list)
    preview: bool
    message: str


class JobBulkRestoreRequest(BaseModel):
    job_ids: list[int] = Field(min_length=1, max_length=500)

    @field_validator("job_ids")
    @classmethod
    def normalize_job_ids(cls, values: list[int]) -> list[int]:
        if any(value <= 0 for value in values):
            raise ValueError("job_ids must contain positive integers")
        return list(dict.fromkeys(values))


class JobBulkRestoreRead(BaseModel):
    restored_count: int
    restored_job_ids: list[int]
    message: str
