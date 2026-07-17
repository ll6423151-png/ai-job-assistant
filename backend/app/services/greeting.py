from app.models.job import Job
from app.models.match_analysis import MatchAnalysis
from app.models.resume import Resume
from app.models.user_profile import UserProfile


def build_greeting(
    job: Job,
    resume: Resume,
    profile: UserProfile | None,
    analysis: MatchAnalysis | None,
    tone: str,
) -> str:
    name_part = f"我是{profile.full_name}，" if profile and profile.full_name else ""
    company_part = f"{job.company_name}的" if job.company_name else "贵公司的"
    role = resume.target_role or job.title
    matched_keywords = analysis.matched_keywords[:3] if analysis else []
    evidence_part = (
        f"简历中包含{'、'.join(matched_keywords)}相关学习或实践内容"
        if matched_keywords
        else "已根据岗位要求整理好相关简历"
    )
    portfolio_part = (
        "，也可提供作品集供参考" if profile and profile.portfolio_url else ""
    )

    if tone == "concise":
        return (
            f"您好，{name_part}希望应聘{company_part}「{job.title}」。"
            f"我的求职方向是{role}，{evidence_part}{portfolio_part}，期待进一步沟通，谢谢。"
        )
    if tone == "warm":
        return (
            f"您好，{name_part}看到{company_part}「{job.title}」岗位后很想进一步了解。"
            f"我的求职方向是{role}，{evidence_part}{portfolio_part}。"
            "如有机会，希望能和您进一步沟通岗位需求，感谢您的时间。"
        )
    return (
        f"您好，{name_part}希望应聘{company_part}「{job.title}」岗位。"
        f"我的求职方向是{role}，{evidence_part}{portfolio_part}。"
        "相关经历已整理在简历中，希望有机会进一步沟通，谢谢。"
    )
