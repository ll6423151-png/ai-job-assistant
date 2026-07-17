import re

from app.models.match_analysis import MatchAnalysis
from app.models.resume import Resume


SECTION_HINTS = ("教育背景", "专业技能", "项目经历")


def normalize_content(content: str) -> str:
    lines = [line.rstrip() for line in content.strip().splitlines()]
    normalized: list[str] = []
    previous_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        normalized.append(line)
        previous_blank = blank
    return "\n".join(normalized).strip()


def build_optimization_draft(
    analysis: MatchAnalysis, resume: Resume
) -> tuple[str, list[str], list[str]]:
    proposed_content = normalize_content(resume.content)
    suggestions = list(analysis.recommendations)
    warnings: list[str] = []

    if resume.target_role and resume.target_role not in proposed_content[:200]:
        target_line = f"求职目标：{resume.target_role}"
        proposed_content = (
            f"{target_line}\n\n{proposed_content}" if proposed_content else target_line
        )
        suggestions.insert(0, f"在简历开头明确求职目标：{resume.target_role}。")

    missing_sections = [
        section for section in SECTION_HINTS if section not in proposed_content
    ]
    if missing_sections:
        suggestions.append(
            f"检查并补充简历结构：{'、'.join(missing_sections)}。"
        )

    if proposed_content and not re.search(r"\d", proposed_content):
        suggestions.append("在确有数据依据时，补充播放量、效率、场次等量化结果。")

    if len(proposed_content) < 200:
        suggestions.append("当前正文较短，优先补充与目标岗位直接相关的真实项目证据。")

    if analysis.missing_keywords:
        warnings.append(
            "以下关键词未在原简历中识别到，不会自动写入："
            + "、".join(analysis.missing_keywords)
            + "。"
        )
    warnings.append("应用前请逐项确认建议稿内容真实、准确且可在面试中说明。")

    return proposed_content, list(dict.fromkeys(suggestions)), warnings
