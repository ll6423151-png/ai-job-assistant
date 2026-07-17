from typing import TypedDict

from app.models.job import Job
from app.models.resume import Resume


OPERATIONS_KEYWORDS = (
    "短视频",
    "直播",
    "内容运营",
    "账号运营",
    "拍摄",
    "剪辑",
    "剪映",
    "Premiere",
    "达芬奇",
    "AE",
    "PS",
    "OBS",
    "抖音",
    "千川",
    "抖+",
    "蝉妈妈",
    "数据分析",
    "Excel",
    "选题",
    "脚本",
    "评论",
    "私信",
    "复盘",
    "投流",
    "选品",
    "场控",
    "中控",
    "直播伴侣",
    "SOP",
    "ROI",
)


class MatchResult(TypedDict):
    score: int
    matched_keywords: list[str]
    missing_keywords: list[str]
    reasons: list[str]
    recommendations: list[str]


def _contains(text: str, keyword: str) -> bool:
    return keyword.casefold() in text.casefold()


def _find_keywords(text: str) -> list[str]:
    return [keyword for keyword in OPERATIONS_KEYWORDS if _contains(text, keyword)]


def build_match_result(job: Job, resume: Resume) -> MatchResult:
    job_text = " ".join(
        [job.title, job.description, job.degree_required, job.experience_required]
    )
    resume_text = " ".join([resume.target_role, resume.content, resume.notes])
    required_keywords = _find_keywords(job_text)
    resume_keywords = _find_keywords(resume_text)
    matched_keywords = [
        keyword for keyword in required_keywords if keyword in resume_keywords
    ]
    missing_keywords = [
        keyword for keyword in required_keywords if keyword not in resume_keywords
    ]

    keyword_score = (
        round(len(matched_keywords) / len(required_keywords) * 70)
        if required_keywords
        else 0
    )
    role_terms = _find_keywords(resume.target_role)
    role_hits = [keyword for keyword in role_terms if _contains(job.title, keyword)]
    role_score = 20 if role_hits else 0
    evidence_score = 10 if resume.content.strip() else 0
    score = min(100, keyword_score + role_score + evidence_score)

    reasons: list[str] = []
    if required_keywords:
        reasons.append(
            f"识别到 {len(required_keywords)} 项相关关键词，简历覆盖 {len(matched_keywords)} 项。"
        )
    else:
        reasons.append("JD 中未识别到预设运营关键词，当前分数仅供参考。")
    if role_hits:
        reasons.append(f"目标岗位与职位标题有相关词匹配：{'、'.join(role_hits)}。")
    else:
        reasons.append("简历目标岗位与职位标题暂未形成直接关键词匹配。")
    if resume.content.strip():
        reasons.append("简历正文已有内容，可继续核对经历与 JD 要求的对应证据。")
    else:
        reasons.append("简历正文为空，暂时无法判断项目经历和工具证据。")

    recommendations = [
        f"仅在确有相关经历时，在简历中补充“{keyword}”的具体项目或结果。"
        for keyword in missing_keywords[:5]
    ]
    if not recommendations:
        recommendations.append("继续用量化结果和具体工具说明已有经历，避免只罗列技能名称。")

    return {
        "score": score,
        "matched_keywords": matched_keywords,
        "missing_keywords": missing_keywords,
        "reasons": reasons,
        "recommendations": recommendations,
    }
