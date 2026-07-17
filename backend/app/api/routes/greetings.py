from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.greeting_message import GreetingMessage
from app.models.job import Job
from app.models.match_analysis import MatchAnalysis
from app.models.resume import Resume
from app.models.user_profile import UserProfile
from app.schemas.greeting_message import GreetingApprove, GreetingCreate, GreetingRead, GreetingUpdate
from app.services.greeting import build_greeting
router = APIRouter()

@router.get('/greetings', response_model=list[GreetingRead])
async def list_greetings(db: AsyncSession=Depends(get_db)) -> list[GreetingMessage]:
    statement = select(GreetingMessage).order_by(desc(GreetingMessage.updated_at), desc(GreetingMessage.id))
    return list((await db.scalars(statement)).all())

@router.post('/greetings', response_model=GreetingRead, status_code=status.HTTP_201_CREATED)
async def create_greeting(payload: GreetingCreate, db: AsyncSession=Depends(get_db)) -> GreetingMessage:
    job = await db.get(Job, payload.job_id)
    if job is None or job.is_archived:
        raise HTTPException(status_code=404, detail='Job not found')
    resume = await db.get(Resume, payload.resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail='Resume not found')
    analysis = await db.scalar(select(MatchAnalysis).where(MatchAnalysis.job_id == job.id, MatchAnalysis.resume_id == resume.id).order_by(desc(MatchAnalysis.created_at), desc(MatchAnalysis.id)))
    profile = await db.scalar(select(UserProfile).limit(1))
    message = GreetingMessage(job_id=job.id, resume_id=resume.id, match_id=analysis.id if analysis else None, job_title=job.title, company_name=job.company_name, resume_title=resume.title, tone=payload.tone, content=build_greeting(job, resume, profile, analysis, payload.tone), status='draft')
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message

@router.get('/greetings/{greeting_id}', response_model=GreetingRead)
async def read_greeting(greeting_id: int, db: AsyncSession=Depends(get_db)) -> GreetingMessage:
    message = await db.get(GreetingMessage, greeting_id)
    if message is None:
        raise HTTPException(status_code=404, detail='Greeting not found')
    return message

@router.put('/greetings/{greeting_id}', response_model=GreetingRead)
async def update_greeting(greeting_id: int, payload: GreetingUpdate, db: AsyncSession=Depends(get_db)) -> GreetingMessage:
    message = await db.get(GreetingMessage, greeting_id)
    if message is None:
        raise HTTPException(status_code=404, detail='Greeting not found')
    if message.status != 'draft':
        raise HTTPException(status_code=409, detail='Approved greeting cannot be edited')
    message.content = payload.content
    await db.commit()
    await db.refresh(message)
    return message

@router.post('/greetings/{greeting_id}/approve', response_model=GreetingRead)
async def approve_greeting(greeting_id: int, payload: GreetingApprove, db: AsyncSession=Depends(get_db)) -> GreetingMessage:
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail='Explicit confirmation is required')
    message = await db.get(GreetingMessage, greeting_id)
    if message is None:
        raise HTTPException(status_code=404, detail='Greeting not found')
    if message.status != 'draft':
        raise HTTPException(status_code=409, detail='Greeting is already approved')
    message.status = 'approved'
    await db.commit()
    await db.refresh(message)
    return message

@router.delete('/greetings/{greeting_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_greeting(greeting_id: int, db: AsyncSession=Depends(get_db)) -> Response:
    message = await db.get(GreetingMessage, greeting_id)
    if message is None:
        raise HTTPException(status_code=404, detail='Greeting not found')
    await db.delete(message)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
