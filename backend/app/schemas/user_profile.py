from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class UserProfileBase(BaseModel):
    full_name: str = Field(default="", max_length=80)
    email: str = Field(default="", max_length=120)
    phone: str = Field(default="", max_length=30)
    current_city: str = Field(default="", max_length=80)
    preferred_cities: list[str] = Field(default_factory=list, max_length=10)
    target_roles: list[str] = Field(default_factory=list, max_length=10)
    salary_min: int | None = Field(default=None, ge=0, le=1_000_000)
    salary_max: int | None = Field(default=None, ge=0, le=1_000_000)
    degree: str = Field(default="", max_length=40)
    experience_level: str = Field(default="", max_length=40)
    company_sizes: list[str] = Field(default_factory=list, max_length=10)
    portfolio_url: str = Field(default="", max_length=500)
    summary: str = Field(default="", max_length=500)

    @field_validator(
        "full_name",
        "email",
        "phone",
        "current_city",
        "degree",
        "experience_level",
        "portfolio_url",
        "summary",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("preferred_cities", "target_roles", "company_sizes")
    @classmethod
    def clean_list(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        return list(dict.fromkeys(cleaned))

    @model_validator(mode="after")
    def validate_salary_range(self) -> "UserProfileBase":
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min cannot exceed salary_max")
        return self


class UserProfileCreate(UserProfileBase):
    pass


class UserProfileUpdate(UserProfileBase):
    pass


class UserProfileRead(UserProfileBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
