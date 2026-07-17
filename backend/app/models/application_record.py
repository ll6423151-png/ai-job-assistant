from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.tenant import TenantOwned


class ApplicationRecord(TenantOwned, Base):
    __tablename__ = "application_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(Integer)
    resume_id: Mapped[int] = mapped_column(Integer)
    greeting_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    job_title: Mapped[str] = mapped_column(String(160), default="")
    company_name: Mapped[str] = mapped_column(String(160), default="")
    resume_title: Mapped[str] = mapped_column(String(120), default="")
    channel: Mapped[str] = mapped_column(String(80), default="manual")
    status: Mapped[str] = mapped_column(String(20), default="prepared")
    confirmed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str] = mapped_column(Text, default="")
    status_history: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
