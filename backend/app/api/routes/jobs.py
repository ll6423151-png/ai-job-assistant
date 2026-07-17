from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.blacklist_company import BlacklistCompany
from app.models.job import Job
from app.schemas.job import JobBulkDeleteRead, JobBulkDeleteRequest, JobBulkRestoreRead, JobBulkRestoreRequest, JobCreate, JobRead, JobUpdate
router = APIRouter()

@router.get('/jobs', response_model=list[JobRead])
async def list_jobs(keyword: str | None=None, city: str | None=None, salary_min: int | None=None, salary_max: int | None=None, degree: str | None=None, experience: str | None=None, company_size: str | None=None, include_blacklisted: bool=False, favorite_only: bool=False, db: AsyncSession=Depends(get_db)) -> list[Job]:
    statement = select(Job).where(Job.status == 'open', Job.is_archived.is_(False))
    if favorite_only:
        statement = statement.where(Job.is_favorite.is_(True))
    if keyword and keyword.strip():
        search = f'%{keyword.strip()}%'
        statement = statement.where(or_(Job.title.ilike(search), Job.company_name.ilike(search), Job.description.ilike(search)))
    if city and city.strip():
        statement = statement.where(Job.city.ilike(f'%{city.strip()}%'))
    if salary_min is not None:
        statement = statement.where(or_(Job.salary_max.is_(None), Job.salary_max >= salary_min))
    if salary_max is not None:
        statement = statement.where(or_(Job.salary_min.is_(None), Job.salary_min <= salary_max))
    if degree and degree.strip():
        statement = statement.where(Job.degree_required == degree.strip())
    if experience and experience.strip():
        statement = statement.where(Job.experience_required == experience.strip())
    if company_size and company_size.strip():
        statement = statement.where(Job.company_size == company_size.strip())
    if not include_blacklisted:
        rules = (await db.scalars(select(BlacklistCompany).where(BlacklistCompany.is_active.is_(True)))).all()
        for rule in rules:
            if rule.match_type == 'contains':
                statement = statement.where(~Job.company_name.ilike(f'%{rule.company_name}%'))
            else:
                statement = statement.where(Job.company_name.ilike(rule.company_name) == False)
    statement = statement.order_by(desc(Job.updated_at), desc(Job.id))
    return list((await db.scalars(statement)).all())

@router.post('/jobs', response_model=JobRead, status_code=status.HTTP_201_CREATED)
async def create_job(payload: JobCreate, db: AsyncSession=Depends(get_db)) -> Job:
    job = Job(**payload.model_dump())
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job

@router.post('/jobs/bulk-delete', response_model=JobBulkDeleteRead)
async def bulk_delete_jobs(payload: JobBulkDeleteRequest, db: AsyncSession=Depends(get_db)) -> JobBulkDeleteRead:
    if payload.delete_all_imported:
        statement = select(Job).where(Job.is_archived.is_(False), or_(Job.source_platform == '智联招聘', Job.source_url.ilike('%zhaopin.com/%')))
    else:
        statement = select(Job).where(Job.id.in_(payload.job_ids), Job.is_archived.is_(False))
    jobs = list((await db.scalars(statement)).all())
    if payload.preview:
        return JobBulkDeleteRead(matched_count=len(jobs), cleared_count=0, cleared_job_ids=[], preview=True, message=f'将从职位列表清除 {len(jobs)} 个岗位。')
    for job in jobs:
        job.is_archived = True
        job.is_favorite = False
    await db.commit()
    return JobBulkDeleteRead(matched_count=len(jobs), cleared_count=len(jobs), cleared_job_ids=[job.id for job in jobs], preview=False, message=f'已从职位列表清除 {len(jobs)} 个岗位，历史记录已保留。')

@router.post('/jobs/bulk-restore', response_model=JobBulkRestoreRead)
async def bulk_restore_jobs(payload: JobBulkRestoreRequest, db: AsyncSession=Depends(get_db)) -> JobBulkRestoreRead:
    jobs = list((await db.scalars(select(Job).where(Job.id.in_(payload.job_ids), Job.is_archived.is_(True)))).all())
    for job in jobs:
        job.is_archived = False
    await db.commit()
    return JobBulkRestoreRead(restored_count=len(jobs), restored_job_ids=[job.id for job in jobs], message=f'已恢复 {len(jobs)} 个岗位到职位列表。')

@router.post('/jobs/{job_id}/favorite', response_model=JobRead)
async def set_job_favorite(job_id: int, favorite: bool=True, db: AsyncSession=Depends(get_db)) -> Job:
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail='Job not found')
    job.is_favorite = favorite
    await db.commit()
    await db.refresh(job)
    return job

@router.get('/jobs/{job_id}', response_model=JobRead)
async def read_job(job_id: int, db: AsyncSession=Depends(get_db)) -> Job:
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail='Job not found')
    return job

@router.put('/jobs/{job_id}', response_model=JobRead)
async def update_job(job_id: int, payload: JobUpdate, db: AsyncSession=Depends(get_db)) -> Job:
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail='Job not found')
    for field, value in payload.model_dump().items():
        setattr(job, field, value)
    await db.commit()
    await db.refresh(job)
    return job

@router.delete('/jobs/{job_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: int, db: AsyncSession=Depends(get_db)) -> Response:
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail='Job not found')
    await db.delete(job)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
