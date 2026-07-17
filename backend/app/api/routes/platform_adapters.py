from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.job import Job
from app.platforms import adapter_registry
from app.platforms.base import PlatformAdapter
from app.schemas.platform_adapter import AdapterImportRequest, AdapterImportResult, AdapterPreview, AdapterPreviewRequest, PlatformAdapterInfo
router = APIRouter()

def adapter_info(adapter: PlatformAdapter) -> PlatformAdapterInfo:
    return PlatformAdapterInfo(key=adapter.key, name=adapter.name, description=adapter.description, capabilities=list(adapter.capabilities), supports_external_search=adapter.supports_external_search, supports_application_submit=adapter.supports_application_submit)

def require_adapter(adapter_key: str) -> PlatformAdapter:
    adapter = adapter_registry.get(adapter_key)
    if adapter is None:
        raise HTTPException(status_code=404, detail='Platform adapter not found')
    return adapter

@router.get('/platform-adapters', response_model=list[PlatformAdapterInfo])
def list_platform_adapters() -> list[PlatformAdapterInfo]:
    return [adapter_info(adapter) for adapter in adapter_registry.all()]

@router.post('/platform-adapters/{adapter_key}/preview', response_model=AdapterPreview)
def preview_adapter_job(adapter_key: str, payload: AdapterPreviewRequest) -> AdapterPreview:
    adapter = require_adapter(adapter_key)
    normalized = adapter.normalize_job(payload.job)
    return AdapterPreview(adapter=adapter_info(adapter), normalized_job=normalized, warnings=adapter.warnings(normalized))

@router.post('/platform-adapters/{adapter_key}/import', response_model=AdapterImportResult, status_code=status.HTTP_201_CREATED)
async def import_adapter_job(adapter_key: str, payload: AdapterImportRequest, db: AsyncSession=Depends(get_db)) -> AdapterImportResult:
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail='Explicit confirmation is required')
    adapter = require_adapter(adapter_key)
    normalized = adapter.normalize_job(payload.job)
    job = Job(**normalized.model_dump())
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return AdapterImportResult(adapter_key=adapter.key, job=job, message='职位已导入本地职位库；未执行外部搜索或投递。')
