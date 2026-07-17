from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.blacklist_company import BlacklistCompany
from app.schemas.blacklist_company import BlacklistCheck, BlacklistCompanyCreate, BlacklistCompanyRead, BlacklistCompanyUpdate
from app.schemas.job_keyword import JobKeywordCreate, JobKeywordRead
from app.services.job_keywords import JOB_KEYWORD_PREFIX, decode_job_keyword, encode_job_keyword
router = APIRouter()

def company_matches(rule: BlacklistCompany, company_name: str) -> bool:
    candidate = company_name.strip().casefold()
    blocked = rule.company_name.strip().casefold()
    if not candidate or not blocked:
        return False
    if rule.match_type == 'contains':
        return blocked in candidate
    return blocked == candidate

async def find_match(db: AsyncSession, company_name: str) -> BlacklistCompany | None:
    rules = (await db.scalars(select(BlacklistCompany).where(BlacklistCompany.is_active.is_(True)).order_by(desc(BlacklistCompany.updated_at), desc(BlacklistCompany.id)))).all()
    return next((rule for rule in rules if company_matches(rule, company_name)), None)

@router.get('/blacklist', response_model=list[BlacklistCompanyRead])
async def list_blacklist(db: AsyncSession=Depends(get_db)) -> list[BlacklistCompany]:
    statement = select(BlacklistCompany).where(~BlacklistCompany.company_name.startswith(JOB_KEYWORD_PREFIX)).order_by(desc(BlacklistCompany.updated_at), desc(BlacklistCompany.id))
    return list((await db.scalars(statement)).all())

def _keyword_read(rule: BlacklistCompany) -> JobKeywordRead:
    return JobKeywordRead(id=rule.id, keyword=decode_job_keyword(rule.company_name), is_active=rule.is_active, created_at=rule.created_at, updated_at=rule.updated_at)

@router.get('/job-keywords', response_model=list[JobKeywordRead])
async def list_job_keywords(db: AsyncSession=Depends(get_db)) -> list[JobKeywordRead]:
    rules = (await db.scalars(select(BlacklistCompany).where(BlacklistCompany.company_name.startswith(JOB_KEYWORD_PREFIX)).order_by(desc(BlacklistCompany.updated_at)))).all()
    return [_keyword_read(rule) for rule in rules]

@router.post('/job-keywords', response_model=JobKeywordRead, status_code=status.HTTP_201_CREATED)
async def create_job_keyword(payload: JobKeywordCreate, db: AsyncSession=Depends(get_db)) -> JobKeywordRead:
    encoded = encode_job_keyword(payload.keyword)
    existing = await db.scalar(select(BlacklistCompany).where(func.lower(BlacklistCompany.company_name) == encoded.casefold()))
    if existing:
        raise HTTPException(status_code=409, detail='该岗位屏蔽关键词已存在')
    rule = BlacklistCompany(company_name=encoded, match_type='exact', reason=f'岗位关键词屏蔽：{payload.keyword}', is_active=payload.is_active)
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return _keyword_read(rule)

@router.put('/job-keywords/{rule_id}', response_model=JobKeywordRead)
async def update_job_keyword(rule_id: int, payload: JobKeywordCreate, db: AsyncSession=Depends(get_db)) -> JobKeywordRead:
    rule = await db.get(BlacklistCompany, rule_id)
    if rule is None or not rule.company_name.startswith(JOB_KEYWORD_PREFIX):
        raise HTTPException(status_code=404, detail='岗位屏蔽关键词不存在')
    rule.company_name = encode_job_keyword(payload.keyword)
    rule.reason = f'岗位关键词屏蔽：{payload.keyword}'
    rule.is_active = payload.is_active
    await db.commit()
    await db.refresh(rule)
    return _keyword_read(rule)

@router.delete('/job-keywords/{rule_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_keyword(rule_id: int, db: AsyncSession=Depends(get_db)) -> Response:
    rule = await db.get(BlacklistCompany, rule_id)
    if rule is None or not rule.company_name.startswith(JOB_KEYWORD_PREFIX):
        raise HTTPException(status_code=404, detail='岗位屏蔽关键词不存在')
    await db.delete(rule)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get('/blacklist/check', response_model=BlacklistCheck)
async def check_blacklist(company_name: str=Query(min_length=1, max_length=160), db: AsyncSession=Depends(get_db)) -> BlacklistCheck:
    rule = await find_match(db, company_name)
    return BlacklistCheck(company_name=company_name.strip(), matched=rule is not None, reason=rule.reason if rule else None, rule_id=rule.id if rule else None, match_type=rule.match_type if rule else None)

@router.post('/blacklist', response_model=BlacklistCompanyRead, status_code=status.HTTP_201_CREATED)
async def create_blacklist_rule(payload: BlacklistCompanyCreate, db: AsyncSession=Depends(get_db)) -> BlacklistCompany:
    existing = await db.scalar(select(BlacklistCompany).where(BlacklistCompany.company_name == payload.company_name))
    if existing is not None:
        raise HTTPException(status_code=409, detail='Company already has a blacklist rule')
    rule = BlacklistCompany(**payload.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule

@router.get('/blacklist/{rule_id}', response_model=BlacklistCompanyRead)
async def read_blacklist_rule(rule_id: int, db: AsyncSession=Depends(get_db)) -> BlacklistCompany:
    rule = await db.get(BlacklistCompany, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail='Blacklist rule not found')
    return rule

@router.put('/blacklist/{rule_id}', response_model=BlacklistCompanyRead)
async def update_blacklist_rule(rule_id: int, payload: BlacklistCompanyUpdate, db: AsyncSession=Depends(get_db)) -> BlacklistCompany:
    rule = await db.get(BlacklistCompany, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail='Blacklist rule not found')
    duplicate = await db.scalar(select(BlacklistCompany).where(BlacklistCompany.company_name == payload.company_name, BlacklistCompany.id != rule_id))
    if duplicate is not None:
        raise HTTPException(status_code=409, detail='Company already has a blacklist rule')
    for field, value in payload.model_dump().items():
        setattr(rule, field, value)
    await db.commit()
    await db.refresh(rule)
    return rule

@router.delete('/blacklist/{rule_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_blacklist_rule(rule_id: int, db: AsyncSession=Depends(get_db)) -> Response:
    rule = await db.get(BlacklistCompany, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail='Blacklist rule not found')
    await db.delete(rule)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
