from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.job import Job
from app.models.match_analysis import MatchAnalysis
from app.models.resume import Resume
from app.schemas.match_analysis import MatchRead, MatchRequest
from app.services.matching import build_match_result
router = APIRouter()

@router.get('/matches', response_model=list[MatchRead])
async def list_matches(db: AsyncSession=Depends(get_db)) -> list[MatchAnalysis]:
    statement = select(MatchAnalysis).order_by(desc(MatchAnalysis.created_at), desc(MatchAnalysis.id))
    return list((await db.scalars(statement)).all())

@router.post('/matches', response_model=MatchRead, status_code=status.HTTP_201_CREATED)
async def create_match_analysis(payload: MatchRequest, db: AsyncSession=Depends(get_db)) -> MatchAnalysis:
    job = await db.get(Job, payload.job_id)
    if job is None or job.is_archived:
        raise HTTPException(status_code=404, detail='Job not found')
    resume = await db.get(Resume, payload.resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail='Resume not found')
    result = build_match_result(job, resume)
    analysis = MatchAnalysis(job_id=job.id, resume_id=resume.id, job_title=job.title, resume_title=resume.title, **result)
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)
    return analysis

@router.get('/matches/{match_id}', response_model=MatchRead)
async def read_match(match_id: int, db: AsyncSession=Depends(get_db)) -> MatchAnalysis:
    analysis = await db.get(MatchAnalysis, match_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail='Match analysis not found')
    return analysis

@router.delete('/matches/{match_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_match(match_id: int, db: AsyncSession=Depends(get_db)) -> Response:
    analysis = await db.get(MatchAnalysis, match_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail='Match analysis not found')
    await db.delete(analysis)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
