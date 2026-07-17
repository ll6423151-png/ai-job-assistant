from typing import TypedDict

from app.models.job import Job
from app.models.resume import Resume


OPERATIONS_KEYWORDS: dict[str, tuple[str, ...]] = {
    "短视频": ("短视频", "视频内容", "short video", "social video"),
    "直播": ("直播", "直播间", "live stream", "livestream"),
    "内容运营": ("内容运营", "内容策划", "内容规划", "选题策划", "content operations", "content strategy", "content planning"),
    "账号运营": ("账号运营", "账号维护", "社媒运营", "social media", "account operations"),
    "拍摄": ("拍摄", "摄影", "摄像", "shooting", "videography"),
    "剪辑": ("剪辑", "视频编辑", "video editing"),
    "剪映": ("剪映", "capcut"),
    "Premiere": ("premiere", "pr剪辑"),
    "达芬奇": ("达芬奇", "davinci resolve"),
    "AE": ("after effects", "ae动效", "ae动画"),
    "PS": ("photoshop", "ps修图"),
    "OBS": ("obs",),
    "抖音": ("抖音", "douyin", "tiktok"),
    "千川": ("千川",),
    "抖+": ("抖+", "dou+"),
    "蝉妈妈": ("蝉妈妈",),
    "数据分析": ("数据分析", "数据复盘", "指标分析", "analytics", "data analysis", "analytics review"),
    "Excel": ("excel", "电子表格", "spreadsheet"),
    "选题": ("选题", "选题策划", "topic planning"),
    "脚本": ("脚本", "文案脚本", "script writing"),
    "评论": ("评论运营", "评论区", "community management"),
    "私信": ("私信", "direct message"),
    "复盘": ("复盘", "review", "retrospective"),
    "投流": ("投流", "广告投放", "media buying"),
    "选品": ("选品", "product selection"),
    "场控": ("场控", "直播协作", "live coordination"),
    "中控": ("中控",),
    "直播伴侣": ("直播伴侣",),
    "SOP": ("sop", "标准流程"),
    "ROI": ("roi", "投入产出"),
}


class MatchResult(TypedDict):
    score: int
    matched_keywords: list[str]
    missing_keywords: list[str]
    reasons: list[str]
    recommendations: list[str]


def _contains(text: str, keyword: str) -> bool:
    return keyword.casefold() in text.casefold()


def _find_keywords(text: str) -> list[str]:
    return [
        keyword
        for keyword, aliases in OPERATIONS_KEYWORDS.items()
        if any(_contains(text, alias) for alias in aliases)
    ]


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
    job_role_terms = _find_keywords(job.title)
    role_hits = [keyword for keyword in role_terms if keyword in job_role_terms]
    direct_role_match = bool(
        resume.target_role.strip()
        and (
            _contains(job.title, resume.target_role.strip())
            or _contains(resume.target_role.strip(), job.title.strip())
        )
    )
    role_score = 20 if role_hits or direct_role_match else 0
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
        reasons.append(f"目标岗位与职位标题有相关能力匹配：{'、'.join(role_hits)}。")
    elif direct_role_match:
        reasons.append("目标岗位名称与职位标题直接匹配。")
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
