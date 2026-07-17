from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.match_analysis import MatchAnalysis
from app.models.resume import Resume
from app.models.resume_optimization import ResumeOptimization
from app.schemas.resume_optimization import OptimizationApply, OptimizationCreate, OptimizationRead, OptimizationUpdate
from app.services.optimization import build_optimization_draft
router = APIRouter()

@router.get('/optimizations', response_model=list[OptimizationRead])
async def list_optimizations(db: AsyncSession=Depends(get_db)) -> list[ResumeOptimization]:
    statement = select(ResumeOptimization).order_by(desc(ResumeOptimization.updated_at), desc(ResumeOptimization.id))
    return list((await db.scalars(statement)).all())

@router.post('/optimizations', response_model=OptimizationRead, status_code=status.HTTP_201_CREATED)
async def create_optimization(payload: OptimizationCreate, db: AsyncSession=Depends(get_db)) -> ResumeOptimization:
    analysis = await db.get(MatchAnalysis, payload.match_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail='Match analysis not found')
    resume = await db.get(Resume, analysis.resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail='Resume not found')
    proposed_content, suggestions, warnings = build_optimization_draft(analysis, resume)
    optimization = ResumeOptimization(match_id=analysis.id, job_id=analysis.job_id, resume_id=resume.id, job_title=analysis.job_title, resume_title=resume.title, original_content=resume.content, proposed_content=proposed_content, suggestions=suggestions, warnings=warnings, status='draft')
    db.add(optimization)
    await db.commit()
    await db.refresh(optimization)
    return optimization

@router.get('/optimizations/{optimization_id}', response_model=OptimizationRead)
async def read_optimization(optimization_id: int, db: AsyncSession=Depends(get_db)) -> ResumeOptimization:
    optimization = await db.get(ResumeOptimization, optimization_id)
    if optimization is None:
        raise HTTPException(status_code=404, detail='Optimization not found')
    return optimization

@router.put('/optimizations/{optimization_id}', response_model=OptimizationRead)
async def update_optimization(optimization_id: int, payload: OptimizationUpdate, db: AsyncSession=Depends(get_db)) -> ResumeOptimization:
    optimization = await db.get(ResumeOptimization, optimization_id)
    if optimization is None:
        raise HTTPException(status_code=404, detail='Optimization not found')
    if optimization.status != 'draft':
        raise HTTPException(status_code=409, detail='Only draft optimizations can be edited')
    optimization.proposed_content = payload.proposed_content.strip()
    await db.commit()
    await db.refresh(optimization)
    return optimization

@router.post('/optimizations/{optimization_id}/apply', response_model=OptimizationRead)
async def apply_optimization(optimization_id: int, payload: OptimizationApply, db: AsyncSession=Depends(get_db)) -> ResumeOptimization:
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail='Explicit confirmation is required')
    optimization = await db.get(ResumeOptimization, optimization_id)
    if optimization is None:
        raise HTTPException(status_code=404, detail='Optimization not found')
    if optimization.status != 'draft':
        raise HTTPException(status_code=409, detail='Optimization is no longer a draft')
    resume = await db.get(Resume, optimization.resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail='Resume not found')
    if resume.content != optimization.original_content:
        raise HTTPException(status_code=409, detail='Resume changed after this draft was created; generate a new draft')
    resume.content = optimization.proposed_content
    optimization.status = 'applied'
    await db.commit()
    await db.refresh(optimization)
    return optimization

@router.post('/optimizations/{optimization_id}/reject', response_model=OptimizationRead)
async def reject_optimization(optimization_id: int, db: AsyncSession=Depends(get_db)) -> ResumeOptimization:
    optimization = await db.get(ResumeOptimization, optimization_id)
    if optimization is None:
        raise HTTPException(status_code=404, detail='Optimization not found')
    if optimization.status != 'draft':
        raise HTTPException(status_code=409, detail='Optimization is no longer a draft')
    optimization.status = 'rejected'
    await db.commit()
    await db.refresh(optimization)
    return optimization

@router.delete('/optimizations/{optimization_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_optimization(optimization_id: int, db: AsyncSession=Depends(get_db)) -> Response:
    optimization = await db.get(ResumeOptimization, optimization_id)
    if optimization is None:
        raise HTTPException(status_code=404, detail='Optimization not found')
    await db.delete(optimization)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
