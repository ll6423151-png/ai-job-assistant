from abc import ABC, abstractmethod

from app.schemas.job import JobCreate


class PlatformAdapter(ABC):
    key: str
    name: str
    description: str
    capabilities: tuple[str, ...]
    supports_external_search: bool = False
    supports_application_submit: bool = False
    login_url: str = ""
    allowed_hosts: tuple[str, ...] = ()
    apply_labels: tuple[str, ...] = ()
    confirmation_labels: tuple[str, ...] = ()
    success_markers: tuple[str, ...] = ()
    logged_in_markers: tuple[str, ...] = ()
    logged_out_markers: tuple[str, ...] = ()
    requires_second_confirmation: bool = False

    @abstractmethod
    def normalize_job(self, payload: JobCreate) -> JobCreate:
        raise NotImplementedError

    def warnings(self, payload: JobCreate) -> list[str]:
        warnings: list[str] = []
        if not payload.source_url:
            warnings.append("未填写原始职位链接，后续无法回溯来源页面。")
        if not payload.description:
            warnings.append("职位描述为空，JD 匹配分析的信息会不完整。")
        return warnings
