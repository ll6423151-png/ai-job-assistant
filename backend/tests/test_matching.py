from types import SimpleNamespace

from app.services.matching import build_match_result


def test_matching_understands_common_chinese_synonyms():
    job = SimpleNamespace(
        title="短视频运营实习生",
        description="负责内容策划、视频编辑、账号维护和数据复盘。",
        degree_required="大专",
        experience_required="应届生",
    )
    resume = SimpleNamespace(
        target_role="短视频运营",
        content="负责选题策划、剪辑、账号运营和数据分析，单条播放量达到 2000。",
        notes="",
    )

    result = build_match_result(job, resume)

    assert result["score"] >= 80
    assert {"短视频", "内容运营", "账号运营", "剪辑", "数据分析"}.issubset(result["matched_keywords"])


def test_matching_understands_common_english_synonyms():
    job = SimpleNamespace(
        title="Social Video Operations Intern",
        description="Content planning, video editing, social media and analytics review.",
        degree_required="",
        experience_required="",
    )
    resume = SimpleNamespace(
        target_role="Social Video Operations",
        content="Short video content strategy, video editing, account operations and data analysis.",
        notes="",
    )

    result = build_match_result(job, resume)

    assert result["score"] >= 80
    assert "剪辑" in result["matched_keywords"]
    assert "数据分析" in result["matched_keywords"]
