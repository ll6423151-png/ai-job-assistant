from datetime import date, datetime

from pydantic import BaseModel


class BreakdownItem(BaseModel):
    key: str
    count: int
    percentage: float


class TrendPoint(BaseModel):
    date: date
    count: int


class RecentApplication(BaseModel):
    id: int
    job_title: str
    company_name: str
    status: str
    channel: str
    updated_at: datetime


class AnalyticsOverview(BaseModel):
    generated_at: datetime
    jobs_count: int
    resumes_count: int
    match_analyses_count: int
    applications_total: int
    submitted_count: int
    active_count: int
    response_count: int
    interview_count: int
    offer_count: int
    rejected_count: int
    due_follow_ups: int
    response_rate: float
    interview_rate: float
    offer_rate: float
    average_match_score: float
    status_breakdown: list[BreakdownItem]
    channel_breakdown: list[BreakdownItem]
    score_distribution: list[BreakdownItem]
    submission_trend: list[TrendPoint]
    recent_applications: list[RecentApplication]
