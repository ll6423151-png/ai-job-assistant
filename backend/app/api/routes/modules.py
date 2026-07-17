from fastapi import APIRouter


router = APIRouter()


@router.get("/modules")
def list_modules() -> dict[str, object]:
    return {
        "compliance": {
            "platform_rules": "respect_platform_terms",
            "auto_apply": False,
            "requires_user_confirmation_before_submit": True,
        },
        "modules": [
            {
                "key": "user_center",
                "name": "User Center",
                "status": "completed",
                "purpose": "Account profile, preferences, and security settings.",
            },
            {
                "key": "resume_management",
                "name": "Resume Management",
                "status": "completed",
                "purpose": "Store resume versions, parse content, and track optimization history.",
            },
            {
                "key": "job_search",
                "name": "Job Search",
                "status": "completed",
                "purpose": "Search jobs by title, city, salary, degree, experience, and company size.",
            },
            {
                "key": "company_blacklist",
                "name": "Company Blacklist",
                "status": "completed",
                "purpose": "Filter blocked companies and explain why a job is hidden.",
            },
            {
                "key": "jd_match",
                "name": "JD Match Analysis",
                "status": "completed",
                "purpose": "Score resume-to-JD fit and return evidence-based reasons.",
            },
            {
                "key": "resume_optimization",
                "name": "Resume Optimization",
                "status": "completed",
                "purpose": "Suggest resume edits based on target JD and user-approved facts.",
            },
            {
                "key": "greeting_generation",
                "name": "Greeting Generation",
                "status": "completed",
                "purpose": "Generate recruiter messages tailored to the JD and resume.",
            },
            {
                "key": "application_records",
                "name": "Application Records",
                "status": "completed",
                "purpose": "Track applications, confirmations, outcomes, and follow-ups.",
            },
            {
                "key": "analytics",
                "name": "Data Statistics",
                "status": "completed",
                "purpose": "Show funnel statistics, response rate, and match score trends.",
            },
            {
                "key": "platform_adapters",
                "name": "Platform Adapters",
                "status": "completed",
                "purpose": "Plugin-friendly integration layer for additional recruitment platforms.",
            },
            {
                "key": "mock_interviews",
                "name": "AI Mock Interviews",
                "status": "completed",
                "purpose": "Resume-aware interviews, follow-up questions, voice support, scoring, and history.",
            },
            {
                "key": "application_automation",
                "name": "Application Automation",
                "status": "completed",
                "purpose": "Profile-based Zhaopin job planning, draft queueing, and per-job confirmation.",
            },
        ],
    }
