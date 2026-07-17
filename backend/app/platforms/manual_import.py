from app.platforms.base import PlatformAdapter
from app.schemas.job import JobCreate


class ManualImportAdapter(PlatformAdapter):
    key = "manual_import"
    name = "手动职位导入"
    description = "将用户确认的结构化职位信息规范化后写入职位库。"
    capabilities = ("job_preview", "confirmed_job_import")

    def normalize_job(self, payload: JobCreate) -> JobCreate:
        data = payload.model_dump()
        data["source_platform"] = "手动导入"
        return JobCreate(**data)
