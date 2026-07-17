from collections import Counter
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.application_record import ApplicationRecord
from app.models.job import Job
from app.models.match_analysis import MatchAnalysis
from app.models.resume import Resume
from app.schemas.analytics import AnalyticsOverview, BreakdownItem, RecentApplication, TrendPoint
router = APIRouter()
APPLICATION_STATUSES = ('prepared', 'submitted', 'screening', 'interview', 'offer', 'rejected', 'withdrawn')
TERMINAL_STATUSES = {'offer', 'rejected', 'withdrawn'}
RESPONSE_STATUSES = {'screening', 'interview', 'offer', 'rejected'}

def percentage(count: int, total: int) -> float:
    return round(count / total * 100, 1) if total else 0.0

def aware_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

def build_breakdown(counter: Counter[str], keys: list[str], total: int) -> list[BreakdownItem]:
    return [BreakdownItem(key=key, count=counter.get(key, 0), percentage=percentage(counter.get(key, 0), total)) for key in keys]

@router.get('/analytics/overview', response_model=AnalyticsOverview)
async def analytics_overview(db: AsyncSession=Depends(get_db)) -> AnalyticsOverview:
    now = datetime.now(timezone.utc)
    applications = list((await db.scalars(select(ApplicationRecord).order_by(desc(ApplicationRecord.updated_at), desc(ApplicationRecord.id)))).all())
    matches = list((await db.scalars(select(MatchAnalysis))).all())
    jobs_count = await db.scalar(select(func.count(Job.id))) or 0
    resumes_count = await db.scalar(select(func.count(Resume.id))) or 0
    applications_total = len(applications)
    submitted_records = [record for record in applications if record.confirmed_by_user]
    submitted_count = len(submitted_records)
    active_count = sum((record.status in {'submitted', 'screening', 'interview'} for record in applications))
    response_count = sum((record.status in RESPONSE_STATUSES for record in submitted_records))
    interview_count = sum((any((event.get('status') == 'interview' for event in record.status_history or [])) for record in submitted_records))
    offer_count = sum((record.status == 'offer' for record in submitted_records))
    rejected_count = sum((record.status == 'rejected' for record in submitted_records))
    due_follow_ups = sum((record.next_follow_up_at is not None and aware_utc(record.next_follow_up_at) <= now and (record.status not in TERMINAL_STATUSES) for record in applications))
    status_counter = Counter((record.status for record in applications))
    channel_counter = Counter((record.channel or '未设置' for record in applications))
    channel_keys = [key for key, _ in channel_counter.most_common()]
    score_counter: Counter[str] = Counter()
    for analysis in matches:
        if analysis.score >= 80:
            score_counter['high'] += 1
        elif analysis.score >= 60:
            score_counter['medium'] += 1
        else:
            score_counter['low'] += 1
    start_date = (now - timedelta(days=13)).date()
    submission_counter = Counter((aware_utc(record.applied_at).date() for record in submitted_records if record.applied_at and aware_utc(record.applied_at).date() >= start_date))
    submission_trend = [TrendPoint(date=start_date + timedelta(days=offset), count=submission_counter.get(start_date + timedelta(days=offset), 0)) for offset in range(14)]
    recent_applications = [RecentApplication(id=record.id, job_title=record.job_title, company_name=record.company_name, status=record.status, channel=record.channel, updated_at=record.updated_at) for record in applications[:5]]
    average_match_score = round(sum((analysis.score for analysis in matches)) / len(matches), 1) if matches else 0.0
    return AnalyticsOverview(generated_at=now, jobs_count=jobs_count, resumes_count=resumes_count, match_analyses_count=len(matches), applications_total=applications_total, submitted_count=submitted_count, active_count=active_count, response_count=response_count, interview_count=interview_count, offer_count=offer_count, rejected_count=rejected_count, due_follow_ups=due_follow_ups, response_rate=percentage(response_count, submitted_count), interview_rate=percentage(interview_count, submitted_count), offer_rate=percentage(offer_count, submitted_count), average_match_score=average_match_score, status_breakdown=build_breakdown(status_counter, list(APPLICATION_STATUSES), applications_total), channel_breakdown=build_breakdown(channel_counter, channel_keys, applications_total), score_distribution=build_breakdown(score_counter, ['high', 'medium', 'low'], len(matches)), submission_trend=submission_trend, recent_applications=recent_applications)
