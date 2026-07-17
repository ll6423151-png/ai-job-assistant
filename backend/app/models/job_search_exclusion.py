from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.tenant import TenantOwned


class JobSearchExclusion(TenantOwned, Base):
    __tablename__ = "job_search_exclusions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "search_signature",
            "source_url",
            name="uq_job_search_exclusion_user_signature_url",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    search_signature: Mapped[str] = mapped_column(String(64), index=True)
    source_url: Mapped[str] = mapped_column(String(500))
    title: Mapped[str] = mapped_column(String(160), default="")
    company_name: Mapped[str] = mapped_column(String(160), default="")
    blockers: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
