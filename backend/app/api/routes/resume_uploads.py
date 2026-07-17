from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.db.session import get_db
from app.models.interview import ResumeAsset
from app.models.resume import Resume
from app.schemas.interview import ResumeUploadResult
from app.services.resume_parser import ResumeParseError, parse_resume
router = APIRouter()

@router.post('/resume-uploads', response_model=ResumeUploadResult, status_code=status.HTTP_201_CREATED)
async def upload_resume(file: UploadFile=File(...), title: str=Form(default=''), target_role: str=Form(default=''), is_primary: bool=Form(default=False), db: AsyncSession=Depends(get_db)) -> ResumeUploadResult:
    filename = Path(file.filename or 'resume').name
    max_bytes = settings.resume_upload_max_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail=f'文件不能超过 {settings.resume_upload_max_mb} MB')
    if not content:
        raise HTTPException(status_code=422, detail='上传文件为空')
    try:
        extracted = parse_resume(filename, content)
    except ResumeParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    resume = Resume(title=(title.strip() or Path(filename).stem)[:120], target_role=target_role.strip()[:120], content=extracted, notes=f'由上传文件 {filename} 自动解析', status='draft', is_primary=is_primary)
    db.add(resume)
    await db.flush()
    if is_primary:
        await db.execute(update(Resume).where(Resume.id != resume.id).values(is_primary=False))
    asset = ResumeAsset(resume_id=resume.id, original_filename=filename, content_type=(file.content_type or '')[:120], size_bytes=len(content), parse_status='parsed', extracted_characters=len(extracted))
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return ResumeUploadResult(asset=asset, resume_id=resume.id, title=resume.title, target_role=resume.target_role, extracted_characters=len(extracted))
