from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.tenant import TenantOwned


class AutomatedApplicationTask(TenantOwned, Base):
    __tablename__ = "automated_application_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform_key: Mapped[str] = mapped_column(String(40), index=True)
    job_id: Mapped[int] = mapped_column(Integer)
    resume_id: Mapped[int] = mapped_column(Integer)
    greeting_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    application_record_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    job_title_snapshot: Mapped[str] = mapped_column(String(160))
    company_snapshot: Mapped[str] = mapped_column(String(160), default="")
    job_url_snapshot: Mapped[str] = mapped_column(String(500))
    resume_title_snapshot: Mapped[str] = mapped_column(String(120))
    resume_content_snapshot: Mapped[str] = mapped_column(Text, default="")
    greeting_snapshot: Mapped[str] = mapped_column(Text, default="")
    browser_target_id: Mapped[str] = mapped_column(String(120), default="")
    preview: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    external_result: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    confirmation_token: Mapped[str] = mapped_column(String(80), default="")
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str] = mapped_column(Text, default="")
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
