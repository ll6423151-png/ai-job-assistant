from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


InterviewStatus = Literal["configured", "in_progress", "completed", "cancelled"]
InterviewType = Literal["comprehensive", "behavioral", "professional"]
PressureLevel = Literal["standard", "challenging", "intense"]


class InterviewCreate(BaseModel):
    resume_id: int | None = Field(default=None, ge=1)
    job_id: int | None = Field(default=None, ge=1)
    target_role: str = Field(default="", max_length=160)
    interview_type: InterviewType = "comprehensive"
    pressure_level: PressureLevel = "standard"
    question_count: int = Field(default=6, ge=3, le=12)

    @field_validator("target_role", mode="before")
    @classmethod
    def strip_target_role(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_target(self) -> "InterviewCreate":
        if self.job_id is None and not self.target_role:
            raise ValueError("target_role is required when no job is selected")
        return self


class InterviewSessionRead(BaseModel):
    id: int
    user_profile_id: int
    resume_id: int | None
    job_id: int | None
    resume_title_snapshot: str
    job_title_snapshot: str
    company_snapshot: str
    target_role: str
    interview_type: InterviewType
    pressure_level: PressureLevel
    question_count: int
    status: InterviewStatus
    provider_name: str
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InterviewTurnRead(BaseModel):
    id: int
    session_id: int
    sequence: int
    role: Literal["interviewer", "candidate"]
    kind: Literal["question", "answer"]
    content: str
    request_id: str | None
    pressure_signal: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InterviewReportRead(BaseModel):
    id: int
    session_id: int
    overall_score: int
    dimension_scores: dict[str, int]
    summary: str
    strengths: list[str]
    improvements: list[str]
    evidence: list[str]
    recommended_actions: list[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InterviewDetail(BaseModel):
    session: InterviewSessionRead
    turns: list[InterviewTurnRead]
    report: InterviewReportRead | None = None


class InterviewAnswer(BaseModel):
    content: str = Field(min_length=1, max_length=12_000)
    request_id: str | None = Field(default=None, min_length=8, max_length=80)

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ResumeAssetRead(BaseModel):
    id: int
    resume_id: int | None
    original_filename: str
    content_type: str
    size_bytes: int
    parse_status: str
    extracted_characters: int
    parse_error: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResumeUploadResult(BaseModel):
    asset: ResumeAssetRead
    resume_id: int
    title: str
    target_role: str
    extracted_characters: int


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4_000)
