from __future__ import annotations

from dataclasses import dataclass

from app.models.job import Job
from app.models.user_profile import UserProfile
from app.services.application_automation import validate_platform_url
from app.platforms.base import PlatformAdapter
from app.services.job_keywords import matched_job_keyword


HARD_MINIMUM_SALARY = 3000


@dataclass
class AutoApplyDecision:
    eligible: bool
    score: int
    reasons: list[str]
    blockers: list[str]


def _normalise(value: str) -> str:
    return "".join(value.casefold().split())


def _contains_any(text: str, values: list[str]) -> bool:
    haystack = _normalise(text)
    return any(_normalise(value) in haystack for value in values if value.strip())


def _city_preferences(profile: UserProfile) -> list[str]:
    values = [*profile.preferred_cities, profile.current_city]
    cleaned: list[str] = []
    for value in values:
        city = value.strip()
        if len(city) > 1 and city[0].isascii() and city[0].isalpha() and not city[1].isascii():
            city = city[1:]
        if city and city not in cleaned:
            cleaned.append(city)
    return cleaned


def _degree_matches(job_degree: str, profile_degree: str) -> bool:
    if not profile_degree or not job_degree:
        return True
    job = _normalise(job_degree)
    profile = _normalise(profile_degree)
    if any(token in job for token in ("不限", "学历不限", "经验不限")):
        return True
    if profile in job:
        return True
    # A listing that accepts a higher degree is not a safe match for a lower degree.
    order = ["高中", "中专", "大专", "本科", "硕士", "博士"]
    job_rank = next((index for index, degree in enumerate(order) if degree in job), None)
    profile_rank = next((index for index, degree in enumerate(order) if degree in profile), None)
    return job_rank is not None and profile_rank is not None and job_rank <= profile_rank


def _experience_matches(job_experience: str, profile_experience: str) -> bool:
    if not profile_experience or not job_experience:
        return True
    job = _normalise(job_experience)
    profile = _normalise(profile_experience)
    if any(token in job for token in ("不限", "应届", "实习", "在校")):
        return True
    if "应届" in profile or "实习" in profile:
        return any(token in job for token in ("无经验", "经验不限", "接受实习", "可实习"))
    return _contains_any(job_experience, [profile_experience])


def evaluate_job(
    job: Job,
    profile: UserProfile,
    adapter: PlatformAdapter,
    blacklisted: bool = False,
    target_roles: list[str] | None = None,
    blocked_keywords: list[str] | None = None,
) -> AutoApplyDecision:
    reasons: list[str] = []
    blockers: list[str] = []
    score = 0

    salary_floor = max(HARD_MINIMUM_SALARY, profile.salary_min or HARD_MINIMUM_SALARY)
    if blacklisted:
        blockers.append("公司在黑名单中")
    if not job.source_url or not validate_platform_url(job.source_url, adapter):
        blockers.append("缺少有效的智联招聘岗位链接")
    if job.salary_min is None:
        blockers.append(f"薪资下限无法确认达到 {salary_floor} 元")
    elif job.salary_min < salary_floor:
        blockers.append(f"月薪下限 {job.salary_min} 元低于要求 {salary_floor} 元")
    else:
        score += 35
        reasons.append(f"月薪下限达到 {salary_floor} 元要求")

    city_preferences = _city_preferences(profile)
    if city_preferences:
        if _contains_any(job.city, city_preferences):
            score += 20
            reasons.append("工作城市匹配用户偏好")
        else:
            blockers.append("工作城市不匹配用户偏好")

    role_text = " ".join([job.title, job.description])
    blocked_keyword = matched_job_keyword(job.title, job.description, blocked_keywords or [])
    if blocked_keyword:
        blockers.append(f"岗位命中屏蔽关键词：{blocked_keyword}")
    roles = profile.target_roles if target_roles is None else target_roles
    if roles:
        if _contains_any(role_text, roles):
            score += 25
            reasons.append("岗位标题或 JD 命中目标岗位")
        else:
            blockers.append("岗位标题和 JD 未命中目标岗位")

    if _degree_matches(job.degree_required, profile.degree):
        score += 10
        if job.degree_required:
            reasons.append("学历要求与用户学历兼容")
    else:
        blockers.append("学历要求高于用户填写的学历")

    if _experience_matches(job.experience_required, profile.experience_level):
        score += 10
        if job.experience_required:
            reasons.append("经验要求与用户经历兼容")
    else:
        blockers.append("经验要求与用户经历不匹配")

    profile_experience = _normalise(profile.experience_level)
    if ("应届" in profile_experience or "实习" in profile_experience) and any(
        marker in job.title for marker in ("主管", "经理", "总监", "负责人", "资深")
    ):
        blockers.append("岗位职级不适合应届生或实习生")

    if profile.company_sizes and job.company_size:
        if _contains_any(job.company_size, profile.company_sizes):
            score += 5
            reasons.append("公司规模符合用户偏好")

    return AutoApplyDecision(
        eligible=not blockers,
        score=min(100, score),
        reasons=reasons,
        blockers=blockers,
    )
