from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MatchRequest(BaseModel):
    job_id: int = Field(gt=0)
    resume_id: int = Field(gt=0)


class MatchRead(BaseModel):
    id: int
    job_id: int
    resume_id: int
    job_title: str
    resume_title: str
    score: int = Field(ge=0, le=100)
    matched_keywords: list[str]
    missing_keywords: list[str]
    reasons: list[str]
    recommendations: list[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
