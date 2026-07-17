from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.blacklist_company import BlacklistCompany
JOB_KEYWORD_PREFIX = '__job_keyword__:'

def encode_job_keyword(keyword: str) -> str:
    return f'{JOB_KEYWORD_PREFIX}{keyword.strip()}'

def decode_job_keyword(value: str) -> str:
    return value[len(JOB_KEYWORD_PREFIX):] if value.startswith(JOB_KEYWORD_PREFIX) else ''

async def active_job_keywords(db: AsyncSession) -> list[str]:
    rules = (await db.scalars(select(BlacklistCompany).where(BlacklistCompany.is_active.is_(True)))).all()
    return [keyword for rule in rules if (keyword := decode_job_keyword(rule.company_name))]

def matched_job_keyword(title: str, description: str, keywords: list[str]) -> str | None:
    text = ''.join(f'{title} {description}'.casefold().split())
    return next((keyword for keyword in keywords if ''.join(keyword.casefold().split()) in text), None)
