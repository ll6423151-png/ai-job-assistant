from app.schemas.application_record import (
    ApplicationConfirm,
    ApplicationCreate,
    ApplicationEvent,
    ApplicationRead,
    ApplicationStatusUpdate,
    ApplicationUpdate,
)
from app.schemas.analytics import (
    AnalyticsOverview,
    BreakdownItem,
    RecentApplication,
    TrendPoint,
)
from app.schemas.blacklist_company import (
    BlacklistCheck,
    BlacklistCompanyCreate,
    BlacklistCompanyRead,
    BlacklistCompanyUpdate,
)
from app.schemas.greeting_message import (
    GreetingApprove,
    GreetingCreate,
    GreetingRead,
    GreetingUpdate,
)
from app.schemas.job import JobCreate, JobRead, JobUpdate
from app.schemas.match_analysis import MatchRead, MatchRequest
from app.schemas.platform_adapter import (
    AdapterImportRequest,
    AdapterImportResult,
    AdapterPreview,
    AdapterPreviewRequest,
    PlatformAdapterInfo,
)
from app.schemas.resume import ResumeCreate, ResumeRead, ResumeUpdate
from app.schemas.resume_optimization import (
    OptimizationApply,
    OptimizationCreate,
    OptimizationRead,
    OptimizationUpdate,
)
from app.schemas.user_profile import UserProfileCreate, UserProfileRead, UserProfileUpdate

__all__ = [
    "ApplicationConfirm",
    "ApplicationCreate",
    "ApplicationEvent",
    "ApplicationRead",
    "ApplicationStatusUpdate",
    "ApplicationUpdate",
    "AdapterImportRequest",
    "AdapterImportResult",
    "AdapterPreview",
    "AdapterPreviewRequest",
    "AnalyticsOverview",
    "BreakdownItem",
    "BlacklistCheck",
    "BlacklistCompanyCreate",
    "BlacklistCompanyRead",
    "BlacklistCompanyUpdate",
    "GreetingApprove",
    "GreetingCreate",
    "GreetingRead",
    "GreetingUpdate",
    "JobCreate",
    "JobRead",
    "JobUpdate",
    "MatchRead",
    "MatchRequest",
    "OptimizationApply",
    "OptimizationCreate",
    "OptimizationRead",
    "OptimizationUpdate",
    "PlatformAdapterInfo",
    "RecentApplication",
    "ResumeCreate",
    "ResumeRead",
    "ResumeUpdate",
    "TrendPoint",
    "UserProfileCreate",
    "UserProfileRead",
    "UserProfileUpdate",
]
