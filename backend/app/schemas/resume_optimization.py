from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OptimizationCreate(BaseModel):
    match_id: int = Field(gt=0)


class OptimizationUpdate(BaseModel):
    proposed_content: str = Field(max_length=50_000)


class OptimizationApply(BaseModel):
    confirmed: bool


class OptimizationRead(BaseModel):
    id: int
    match_id: int
    job_id: int
    resume_id: int
    job_title: str
    resume_title: str
    original_content: str
    proposed_content: str
    suggestions: list[str]
    warnings: list[str]
    status: Literal["draft", "applied", "rejected"]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
