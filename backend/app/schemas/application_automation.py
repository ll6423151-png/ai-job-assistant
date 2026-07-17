from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AutomationStatus = Literal[
    "draft",
    "awaiting_login",
    "awaiting_confirmation",
    "submitting",
    "submitted",
    "verification_required",
    "failed",
    "cancelled",
]


class AutomationPlatformInfo(BaseModel):
    key: str
    name: str
    description: str
    login_url: str
    capabilities: list[str]
    browser_bridge_available: bool
    daily_submission_limit: int
    cooldown_seconds: int


class LoginStatus(BaseModel):
    platform_key: str
    status: Literal["logged_in", "logged_out", "unknown", "bridge_unavailable"]
    target_id: str | None = None
    evidence: list[str] = []
    message: str


class AutomationTaskCreate(BaseModel):
    platform_key: Literal["zhaopin"]
    job_id: int = Field(gt=0)
    resume_id: int = Field(gt=0)
    greeting_id: int | None = Field(default=None, gt=0)
    greeting_content: str | None = Field(default=None, max_length=1000)


class AutomationTaskRead(BaseModel):
    id: int
    platform_key: str
    job_id: int
    resume_id: int
    greeting_id: int | None
    application_record_id: int | None
    status: AutomationStatus
    job_title_snapshot: str
    company_snapshot: str
    job_url_snapshot: str
    resume_title_snapshot: str
    greeting_snapshot: str
    confirmation_token: str
    preview: dict[str, object]
    external_result: dict[str, object]
    confirmed_by_user: bool
    error_message: str
    prepared_at: datetime | None
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AutomationSubmitRequest(BaseModel):
    confirmed: bool
    confirmation_token: str = Field(min_length=8, max_length=80)


class AutoApplyPlanRequest(BaseModel):
    greeting_content: str | None = Field(default=None, max_length=1000)


class AutoApplyCandidateRead(BaseModel):
    job_id: int
    title: str
    company_name: str
    city: str
    salary_min: int | None
    salary_max: int | None
    source_url: str
    score: int
    reasons: list[str]
    blockers: list[str]
    eligible: bool
    task_id: int | None = None
    task_status: AutomationStatus | None = None


class AutoApplyPlanRead(BaseModel):
    platform_key: Literal["zhaopin"]
    resume_id: int
    resume_title: str
    salary_floor: int
    eligible_count: int
    queued_count: int
    skipped_count: int
    candidates: list[AutoApplyCandidateRead]
    message: str


class AutomationCancelRequest(BaseModel):
    reason: str = Field(default="用户选择不投递", max_length=200)


class ZhaopinSearchImportRequest(BaseModel):
    keyword: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=80)
    page_limit: int = Field(default=3, ge=1, le=5)
    import_limit: int = Field(default=20, ge=1, le=50)


class ZhaopinSearchExclusionClearRequest(BaseModel):
    search_signature: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


class ZhaopinSearchExclusionClearRead(BaseModel):
    deleted_count: int
    message: str


class ZhaopinSearchCandidateRead(BaseModel):
    title: str
    company_name: str
    city: str
    salary_text: str
    salary_min: int | None
    salary_max: int | None
    degree_required: str
    experience_required: str
    company_size: str
    description_loaded: bool
    auto_blacklisted: bool = False
    source_url: str
    eligible: bool
    score: int
    reasons: list[str]
    blockers: list[str]
    job_id: int | None = None
    import_action: Literal["created", "updated"] | None = None


class ZhaopinSearchImportRead(BaseModel):
    query: str
    search_url: str
    pages_requested: int
    scanned_count: int
    eligible_count: int
    created_count: int
    updated_count: int
    auto_blacklisted_count: int
    history_skipped_count: int = 0
    search_signature: str
    candidates: list[ZhaopinSearchCandidateRead]
    message: str


class AutoApplyRunRequest(ZhaopinSearchImportRequest):
    greeting_content: str | None = Field(default=None, max_length=1000)


class AutoApplyRunRead(BaseModel):
    search: ZhaopinSearchImportRead
    plan: AutoApplyPlanRead
    message: str
