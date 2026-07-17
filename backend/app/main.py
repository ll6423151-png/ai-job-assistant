from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    analytics,
    application_automation,
    applications,
    blacklist,
    greetings,
    health,
    interview_audio,
    interviews,
    jobs,
    matches,
    modules,
    optimizations,
    platform_adapters,
    resumes,
    resume_uploads,
    user_profile,
    auth,
)
from app.core.config import settings
from app.db.session import init_db
from app.services.auth import get_current_user


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="AI Job Assistant API",
    version="0.1.0",
    description="Backend API for resume management, job matching, and application workflows.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(auth.router, prefix="/api", tags=["authentication"])
protected = [Depends(get_current_user)]
app.include_router(modules.router, prefix="/api", tags=["modules"], dependencies=protected)
app.include_router(user_profile.router, prefix="/api", tags=["user-center"], dependencies=protected)
app.include_router(resumes.router, prefix="/api", tags=["resume-management"], dependencies=protected)
app.include_router(resume_uploads.router, prefix="/api", tags=["resume-parsing"], dependencies=protected)
app.include_router(interviews.router, prefix="/api", tags=["mock-interviews"], dependencies=protected)
app.include_router(interview_audio.router, prefix="/api", tags=["interview-audio"], dependencies=protected)
app.include_router(jobs.router, prefix="/api", tags=["job-search"], dependencies=protected)
app.include_router(blacklist.router, prefix="/api", tags=["company-blacklist"], dependencies=protected)
app.include_router(matches.router, prefix="/api", tags=["jd-match"], dependencies=protected)
app.include_router(
    optimizations.router, prefix="/api", tags=["resume-optimization"], dependencies=protected
)
app.include_router(greetings.router, prefix="/api", tags=["greeting-generation"], dependencies=protected)
app.include_router(applications.router, prefix="/api", tags=["application-records"], dependencies=protected)
app.include_router(application_automation.router, prefix="/api", tags=["application-automation"], dependencies=protected)
app.include_router(analytics.router, prefix="/api", tags=["analytics"], dependencies=protected)
app.include_router(
    platform_adapters.router, prefix="/api", tags=["platform-adapters"], dependencies=protected
)


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "AI Job Assistant API", "status": "ok"}
