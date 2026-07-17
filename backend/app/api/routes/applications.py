from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.application_record import ApplicationRecord
from app.models.greeting_message import GreetingMessage
from app.models.job import Job
from app.models.resume import Resume
from app.schemas.application_record import ApplicationConfirm, ApplicationCreate, ApplicationRead, ApplicationStatusUpdate, ApplicationUpdate
router = APIRouter()
ALLOWED_TRANSITIONS: dict[str, set[str]] = {'prepared': {'withdrawn'}, 'submitted': {'screening', 'interview', 'offer', 'rejected', 'withdrawn'}, 'screening': {'interview', 'offer', 'rejected', 'withdrawn'}, 'interview': {'offer', 'rejected', 'withdrawn'}, 'offer': set(), 'rejected': set(), 'withdrawn': set()}

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def append_status_event(record: ApplicationRecord, next_status: str, note: str='') -> None:
    event = {'status': next_status, 'timestamp': now_utc().isoformat(), 'note': note}
    record.status_history = [*(record.status_history or []), event]

@router.get('/applications', response_model=list[ApplicationRead])
async def list_applications(application_status: str | None=None, db: AsyncSession=Depends(get_db)) -> list[ApplicationRecord]:
    statement = select(ApplicationRecord)
    if application_status:
        statement = statement.where(ApplicationRecord.status == application_status)
    statement = statement.order_by(desc(ApplicationRecord.updated_at), desc(ApplicationRecord.id))
    return list((await db.scalars(statement)).all())

@router.post('/applications', response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
async def create_application(payload: ApplicationCreate, db: AsyncSession=Depends(get_db)) -> ApplicationRecord:
    job = await db.get(Job, payload.job_id)
    if job is None or job.is_archived:
        raise HTTPException(status_code=404, detail='Job not found')
    resume = await db.get(Resume, payload.resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail='Resume not found')
    if payload.greeting_id is not None:
        greeting = await db.get(GreetingMessage, payload.greeting_id)
        if greeting is None:
            raise HTTPException(status_code=404, detail='Greeting not found')
        if greeting.status != 'approved':
            raise HTTPException(status_code=409, detail='Greeting must be approved')
        if greeting.job_id != job.id or greeting.resume_id != resume.id:
            raise HTTPException(status_code=400, detail='Greeting does not belong to the selected job and resume')
    created_at = now_utc()
    record = ApplicationRecord(job_id=job.id, resume_id=resume.id, greeting_id=payload.greeting_id, job_title=job.title, company_name=job.company_name, resume_title=resume.title, channel=payload.channel or '手动记录', status='prepared', confirmed_by_user=False, next_follow_up_at=payload.next_follow_up_at, notes=payload.notes, status_history=[{'status': 'prepared', 'timestamp': created_at.isoformat(), 'note': '创建待确认投递记录'}])
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record

@router.get('/applications/{application_id}', response_model=ApplicationRead)
async def read_application(application_id: int, db: AsyncSession=Depends(get_db)) -> ApplicationRecord:
    record = await db.get(ApplicationRecord, application_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Application not found')
    return record

@router.put('/applications/{application_id}', response_model=ApplicationRead)
async def update_application(application_id: int, payload: ApplicationUpdate, db: AsyncSession=Depends(get_db)) -> ApplicationRecord:
    record = await db.get(ApplicationRecord, application_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Application not found')
    record.channel = payload.channel or '手动记录'
    record.next_follow_up_at = payload.next_follow_up_at
    record.notes = payload.notes
    await db.commit()
    await db.refresh(record)
    return record

@router.post('/applications/{application_id}/confirm', response_model=ApplicationRead)
async def confirm_application(application_id: int, payload: ApplicationConfirm, db: AsyncSession=Depends(get_db)) -> ApplicationRecord:
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail='Explicit confirmation is required')
    record = await db.get(ApplicationRecord, application_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Application not found')
    if record.status != 'prepared':
        raise HTTPException(status_code=409, detail='Application is not awaiting confirmation')
    record.status = 'submitted'
    record.confirmed_by_user = True
    record.applied_at = now_utc()
    append_status_event(record, 'submitted', '用户确认已完成投递')
    await db.commit()
    await db.refresh(record)
    return record

@router.post('/applications/{application_id}/status', response_model=ApplicationRead)
async def update_application_status(application_id: int, payload: ApplicationStatusUpdate, db: AsyncSession=Depends(get_db)) -> ApplicationRecord:
    record = await db.get(ApplicationRecord, application_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Application not found')
    if payload.status == 'submitted':
        raise HTTPException(status_code=400, detail='Use the confirmation endpoint')
    if payload.status not in ALLOWED_TRANSITIONS.get(record.status, set()):
        raise HTTPException(status_code=409, detail=f'Cannot move application from {record.status} to {payload.status}')
    record.status = payload.status
    append_status_event(record, payload.status, payload.note)
    await db.commit()
    await db.refresh(record)
    return record

@router.delete('/applications/{application_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(application_id: int, db: AsyncSession=Depends(get_db)) -> Response:
    record = await db.get(ApplicationRecord, application_id)
    if record is None:
        raise HTTPException(status_code=404, detail='Application not found')
    await db.delete(record)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
