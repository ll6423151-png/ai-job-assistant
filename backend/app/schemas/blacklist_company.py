from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BlacklistCompanyBase(BaseModel):
    company_name: str = Field(min_length=1, max_length=160)
    match_type: Literal["exact", "contains"] = "exact"
    reason: str = Field(default="", max_length=500)
    is_active: bool = True

    @field_validator("company_name", "reason", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, value: str) -> str:
        if not value:
            raise ValueError("company_name cannot be empty")
        return value


class BlacklistCompanyCreate(BlacklistCompanyBase):
    pass


class BlacklistCompanyUpdate(BlacklistCompanyBase):
    pass


class BlacklistCompanyRead(BlacklistCompanyBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BlacklistCheck(BaseModel):
    company_name: str
    matched: bool
    reason: str | None = None
    rule_id: int | None = None
    match_type: Literal["exact", "contains"] | None = None
