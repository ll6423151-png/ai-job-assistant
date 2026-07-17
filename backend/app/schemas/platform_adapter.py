from pydantic import BaseModel

from app.schemas.job import JobCreate, JobRead


class PlatformAdapterInfo(BaseModel):
    key: str
    name: str
    description: str
    capabilities: list[str]
    supports_external_search: bool
    supports_application_submit: bool


class AdapterPreviewRequest(BaseModel):
    job: JobCreate


class AdapterPreview(BaseModel):
    adapter: PlatformAdapterInfo
    normalized_job: JobCreate
    warnings: list[str]


class AdapterImportRequest(AdapterPreviewRequest):
    confirmed: bool


class AdapterImportResult(BaseModel):
    adapter_key: str
    job: JobRead
    message: str
