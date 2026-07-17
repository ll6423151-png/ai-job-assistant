from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.resume import Resume
from app.schemas.resume import ResumeCreate, ResumeRead, ResumeUpdate
router = APIRouter()

async def clear_other_primary_resumes(db: AsyncSession, current_id: int) -> None:
    await db.execute(update(Resume).where(Resume.id != current_id).values(is_primary=False))

@router.get('/resumes', response_model=list[ResumeRead])
async def list_resumes(db: AsyncSession=Depends(get_db)) -> list[Resume]:
    statement = select(Resume).order_by(desc(Resume.updated_at), desc(Resume.id))
    return list((await db.scalars(statement)).all())

@router.post('/resumes', response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
async def create_resume(payload: ResumeCreate, db: AsyncSession=Depends(get_db)) -> Resume:
    resume = Resume(**payload.model_dump())
    db.add(resume)
    await db.flush()
    if resume.is_primary:
        await clear_other_primary_resumes(db, resume.id)
    await db.commit()
    await db.refresh(resume)
    return resume

@router.get('/resumes/{resume_id}', response_model=ResumeRead)
async def read_resume(resume_id: int, db: AsyncSession=Depends(get_db)) -> Resume:
    resume = await db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail='Resume not found')
    return resume

@router.put('/resumes/{resume_id}', response_model=ResumeRead)
async def update_resume(resume_id: int, payload: ResumeUpdate, db: AsyncSession=Depends(get_db)) -> Resume:
    resume = await db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail='Resume not found')
    for field, value in payload.model_dump().items():
        setattr(resume, field, value)
    if resume.is_primary:
        await clear_other_primary_resumes(db, resume.id)
    await db.commit()
    await db.refresh(resume)
    return resume

@router.delete('/resumes/{resume_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(resume_id: int, db: AsyncSession=Depends(get_db)) -> Response:
    resume = await db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail='Resume not found')
    await db.delete(resume)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
