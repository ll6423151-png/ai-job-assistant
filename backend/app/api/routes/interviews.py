from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.interview import InterviewSession, InterviewTurn
from app.models.job import Job
from app.models.resume import Resume
from app.schemas.interview import InterviewAnswer, InterviewCreate, InterviewDetail, InterviewReportRead, InterviewSessionRead
from app.services.interview import complete_interview, get_report, list_turns, start_interview, submit_answer
router = APIRouter()

async def _get_session(db: AsyncSession, session_id: int) -> InterviewSession:
    interview = await db.get(InterviewSession, session_id)
    if interview is None:
        raise HTTPException(status_code=404, detail='Interview session not found')
    return interview

async def _detail(db: AsyncSession, interview: InterviewSession) -> InterviewDetail:
    return InterviewDetail(session=interview, turns=await list_turns(db, interview.id), report=await get_report(db, interview.id))

@router.get('/interviews', response_model=list[InterviewSessionRead])
async def list_interviews(interview_status: str | None=Query(default=None, alias='status'), db: AsyncSession=Depends(get_db)) -> list[InterviewSession]:
    statement = select(InterviewSession)
    if interview_status:
        statement = statement.where(InterviewSession.status == interview_status)
    return list((await db.scalars(statement.order_by(desc(InterviewSession.updated_at), desc(InterviewSession.id)))).all())

@router.post('/interviews', response_model=InterviewDetail, status_code=status.HTTP_201_CREATED)
async def create_interview(payload: InterviewCreate, db: AsyncSession=Depends(get_db)) -> InterviewDetail:
    resume = await db.get(Resume, payload.resume_id) if payload.resume_id else None
    if payload.resume_id and resume is None:
        raise HTTPException(status_code=404, detail='Resume not found')
    job = await db.get(Job, payload.job_id) if payload.job_id else None
    if payload.job_id and (job is None or job.is_archived):
        raise HTTPException(status_code=404, detail='Job not found')
    target_role = (job.title if job else payload.target_role).strip()
    interview = InterviewSession(resume_id=resume.id if resume else None, job_id=job.id if job else None, resume_title_snapshot=resume.title if resume else '', resume_content_snapshot=resume.content if resume else '', job_title_snapshot=job.title if job else target_role, company_snapshot=job.company_name if job else '', job_description_snapshot=job.description if job else '', target_role=target_role, interview_type=payload.interview_type, pressure_level=payload.pressure_level, question_count=payload.question_count)
    db.add(interview)
    await db.commit()
    await db.refresh(interview)
    return await _detail(db, interview)

@router.get('/interviews/{session_id}', response_model=InterviewDetail)
async def read_interview(session_id: int, db: AsyncSession=Depends(get_db)) -> InterviewDetail:
    return await _detail(db, await _get_session(db, session_id))

@router.post('/interviews/{session_id}/start', response_model=InterviewDetail)
async def start(session_id: int, db: AsyncSession=Depends(get_db)) -> InterviewDetail:
    interview = await _get_session(db, session_id)
    if interview.status == 'cancelled':
        raise HTTPException(status_code=409, detail='Cancelled interview cannot be started')
    await start_interview(db, interview)
    await db.refresh(interview)
    return await _detail(db, interview)

@router.post('/interviews/{session_id}/answers', response_model=InterviewDetail)
async def answer(session_id: int, payload: InterviewAnswer, db: AsyncSession=Depends(get_db)) -> InterviewDetail:
    interview = await _get_session(db, session_id)
    if interview.status != 'in_progress':
        if payload.request_id and await db.scalar(select(InterviewTurn).where(InterviewTurn.session_id == session_id, InterviewTurn.request_id == payload.request_id)):
            return await _detail(db, interview)
        raise HTTPException(status_code=409, detail='Interview is not in progress')
    await submit_answer(db, interview, payload.content, payload.request_id)
    await db.refresh(interview)
    return await _detail(db, interview)

@router.post('/interviews/{session_id}/complete', response_model=InterviewDetail)
async def complete(session_id: int, db: AsyncSession=Depends(get_db)) -> InterviewDetail:
    interview = await _get_session(db, session_id)
    if interview.status == 'cancelled':
        raise HTTPException(status_code=409, detail='Cancelled interview cannot be completed')
    await complete_interview(db, interview)
    await db.refresh(interview)
    return await _detail(db, interview)

@router.post('/interviews/{session_id}/cancel', response_model=InterviewDetail)
async def cancel(session_id: int, db: AsyncSession=Depends(get_db)) -> InterviewDetail:
    interview = await _get_session(db, session_id)
    if interview.status == 'completed':
        raise HTTPException(status_code=409, detail='Completed interview cannot be cancelled')
    if interview.status != 'cancelled':
        interview.status = 'cancelled'
        interview.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(interview)
    return await _detail(db, interview)

@router.get('/interviews/{session_id}/report', response_model=InterviewReportRead)
async def read_report(session_id: int, db: AsyncSession=Depends(get_db)) -> InterviewReportRead:
    await _get_session(db, session_id)
    report = await get_report(db, session_id)
    if report is None:
        raise HTTPException(status_code=404, detail='Interview report not found')
    return InterviewReportRead.model_validate(report)
