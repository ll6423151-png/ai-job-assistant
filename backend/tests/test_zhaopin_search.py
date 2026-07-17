from app.main import app
from app.services.browser_bridge import get_browser_bridge, unwrap_proxy_payload
from app.services.zhaopin_search import (
    _search_url_for_query,
    is_zero_or_unpaid_salary,
    load_job_description,
    parse_monthly_salary,
)


class FreshKeywordBridge:
    def __init__(self) -> None:
        self.closed_targets: list[str] = []
        self.keyword_accepted = False

    def open_url(self, url: str) -> str:
        return "home"

    def close_target(self, target_id: str) -> None:
        self.closed_targets.append(target_id)

    def evaluate(self, target_id: str, script: str):
        if "execCommand('insertText'" in script:
            self.keyword_accepted = True
            return {"search_url": "https://www.zhaopin.com/sou/jl489"}
        if "search-wrapper__word__history__a" in script:
            return {"clicked": False}
        if self.keyword_accepted:
            return {"search_url": "https://www.zhaopin.com/sou/jl489/kwFRESH"}
        return {"search_url": "https://www.zhaopin.com/sou/jl489"}


class FakeZhaopinSearchBridge:
    def __init__(self) -> None:
        self.closed_targets: list[str] = []
        self.description_reads = 0

    def is_available(self) -> bool:
        return True

    def open_url(self, url: str) -> str:
        if url == "https://www.zhaopin.com/":
            return "home"
        if "/jobdetail/" in url:
            return "detail"
        return "search"

    def close_target(self, target_id: str) -> None:
        self.closed_targets.append(target_id)

    def evaluate(self, target_id: str, script: str):
        if "search-wrapper__input" in script:
            return {
                "search_url": "https://www.zhaopin.com/sou/jl489/kwTEST/p1",
                "logged_in": False,
            }
        if "selected_city" in script:
            return {
                "url": "https://www.zhaopin.com/sou/jl551/kwTEST/p1",
                "selected_city": "重庆",
            }
        if "query-location" in script:
            return {"opened": True}
        if "query-city" in script:
            return {
                "clicked": True,
                "url": "https://www.zhaopin.com/sou/jl551/kwTEST/p1",
            }
        if "joblist-box__item" in script:
            return {
                "url": "https://www.zhaopin.com/sou/jl489/kwTEST/p1",
                "items": [
                    {
                        "title": "实习运营",
                        "company_name": "重庆星创传媒有限公司",
                        "city": "重庆·渝中",
                        "salary_text": "4000-8000元",
                        "degree_required": "学历不限",
                        "experience_required": "经验不限",
                        "company_size_raw": "20-99人",
                        "tags": ["抖音"],
                        "source_url": "https://www.zhaopin.com/jobdetail/eligible.htm?refcode=4019",
                    },
                    {
                        "title": "直播运营",
                        "company_name": "上海传媒有限公司",
                        "city": "上海·浦东",
                        "salary_text": "6000-10000元",
                        "degree_required": "大专",
                        "experience_required": "经验不限",
                        "company_size_raw": "20-99人",
                        "tags": ["直播运营"],
                        "source_url": "https://www.zhaopin.com/jobdetail/wrong-city.htm",
                    },
                    {
                        "title": "直播运营实习生",
                        "company_name": "重庆零薪传媒有限公司",
                        "city": "重庆·江北",
                        "salary_text": "无薪",
                        "degree_required": "学历不限",
                        "experience_required": "经验不限",
                        "company_size_raw": "20-99人",
                        "tags": ["直播运营"],
                        "source_url": "https://www.zhaopin.com/jobdetail/unpaid.htm",
                    },
                ],
            }
        if "describtion-card__detail-content" in script:
            self.description_reads += 1
            return {
                "description": "负责直播运营、场控协助和直播数据复盘。",
                "page_title": "直播运营助理招聘",
            }
        return {}


class DelayedDescriptionBridge:
    def __init__(self) -> None:
        self.read_count = 0
        self.closed_targets: list[str] = []

    def open_url(self, url: str) -> str:
        return "detail"

    def close_target(self, target_id: str) -> None:
        self.closed_targets.append(target_id)

    def evaluate(self, target_id: str, script: str):
        self.read_count += 1
        if self.read_count < 3:
            return {"description": "", "verification_required": False}
        return {
            "description": "负责直播运营与直播数据复盘。",
            "verification_required": False,
        }


class ManualKeywordSearchBridge(FakeZhaopinSearchBridge):
    def evaluate(self, target_id: str, script: str):
        if "joblist-box__item" in script:
            return {
                "url": "https://www.zhaopin.com/sou/jl551/kwAI/p1",
                "items": [
                    {
                        "title": "AI漫剧制作师（实习生）",
                        "company_name": "重庆星汇达传媒科技有限公司",
                        "city": "重庆·渝北",
                        "salary_text": "4000-7000元",
                        "degree_required": "大专",
                        "experience_required": "接受实习",
                        "company_size_raw": "20-99人",
                        "tags": ["AI漫剧", "AIGC"],
                        "source_url": "https://www.zhaopin.com/jobdetail/ai-comic.htm",
                    }
                ],
            }
        if "describtion-card__detail-content" in script:
            return {
                "description": "使用 AIGC 工具完成 AI 漫剧画面、分镜和后期制作。",
                "page_title": "AI漫剧制作师招聘",
            }
        return super().evaluate(target_id, script)


def create_search_profile(client):
    response = client.put(
        "/api/user-profile",
        json={
            "current_city": "重庆",
            "preferred_cities": ["c重庆"],
            "target_roles": ["直播运营"],
            "salary_min": 3000,
            "degree": "大专",
            "experience_level": "应届生/实习生",
            "company_sizes": ["中小企业"],
        },
    )
    assert response.status_code == 200


def test_parse_monthly_salary_rejects_unknown_or_non_monthly_pay():
    assert parse_monthly_salary("5000-8000元") == (5000, 8000)
    assert parse_monthly_salary("1-1.3万") == (10000, 13000)
    assert parse_monthly_salary("薪资面议") == (None, None)
    assert parse_monthly_salary("200元/天") == (None, None)


def test_fresh_search_keyword_uses_browser_text_insertion(monkeypatch):
    monkeypatch.setattr("app.services.zhaopin_search.time.sleep", lambda _seconds: None)
    bridge = FreshKeywordBridge()

    search_url = _search_url_for_query(bridge, "AI漫剧")

    assert search_url == "https://www.zhaopin.com/sou/jl489/kwFRESH"
    assert bridge.closed_targets == ["home"]


def test_zero_or_unpaid_salary_detection_is_explicit():
    assert is_zero_or_unpaid_salary("无薪", None, None) is True
    assert is_zero_or_unpaid_salary("0-5000元", 0, 5000) is True
    assert is_zero_or_unpaid_salary("薪资面议", None, None) is False
    assert is_zero_or_unpaid_salary("5000-8000元", 5000, 8000) is False


def test_browser_bridge_unwraps_current_proxy_value_envelope():
    assert unwrap_proxy_payload({"value": {"items": [1]}}) == {"items": [1]}
    assert unwrap_proxy_payload({"result": {"items": [2]}}) == {"items": [2]}


def test_job_description_waits_for_zhaopin_page_hydration():
    bridge = DelayedDescriptionBridge()

    assert load_job_description(bridge, "https://www.zhaopin.com/jobdetail/test.htm") == (
        "负责直播运营与直播数据复盘。"
    )
    assert bridge.read_count == 3
    assert bridge.closed_targets == ["detail"]


def test_zhaopin_search_import_uses_profile_and_avoids_duplicates(client):
    create_search_profile(client)
    bridge = FakeZhaopinSearchBridge()
    app.dependency_overrides[get_browser_bridge] = lambda: bridge
    try:
        first = client.post(
            "/api/application-automation/zhaopin/search-import",
            json={"page_limit": 1, "import_limit": 10},
        )
        assert first.status_code == 200
        result = first.json()
        assert result["query"] == "直播运营"
        assert result["scanned_count"] == 3
        assert result["eligible_count"] == 1
        assert result["created_count"] == 1
        assert result["updated_count"] == 0
        assert result["auto_blacklisted_count"] == 1
        assert result["history_skipped_count"] == 0
        assert len(result["search_signature"]) == 64
        assert result["candidates"][0]["job_id"] is not None
        assert result["candidates"][0]["import_action"] == "created"
        assert result["candidates"][1]["eligible"] is False
        assert "城市" in "".join(result["candidates"][1]["blockers"])
        assert result["candidates"][2]["eligible"] is False
        assert result["candidates"][2]["auto_blacklisted"] is True
        assert "黑名单" in "".join(result["candidates"][2]["blockers"])

        jobs = client.get("/api/jobs").json()
        assert len(jobs) == 1
        assert jobs[0]["title"] == "实习运营"
        assert jobs[0]["company_size"] == "中小企业"
        assert "直播数据复盘" in jobs[0]["description"]

        blacklist = client.get("/api/blacklist").json()
        unpaid_rules = [
            rule
            for rule in blacklist
            if rule["company_name"] == "重庆零薪传媒有限公司"
        ]
        assert len(unpaid_rules) == 1
        assert unpaid_rules[0]["match_type"] == "exact"
        assert unpaid_rules[0]["is_active"] is True
        assert "无薪" in unpaid_rules[0]["reason"]

        second = client.post(
            "/api/application-automation/zhaopin/search-import",
            json={"page_limit": 1, "import_limit": 10},
        )
        assert second.status_code == 200
        assert second.json()["created_count"] == 0
        assert second.json()["updated_count"] == 1
        assert second.json()["history_skipped_count"] == 2
        assert len(second.json()["candidates"]) == 1
        assert second.json()["candidates"][0]["import_action"] == "updated"
        assert bridge.description_reads == 2
        assert len(client.get("/api/blacklist").json()) == 1
        assert len(client.get("/api/jobs").json()) == 1

        cleared = client.post(
            "/api/application-automation/zhaopin/search-exclusions/clear",
            json={"search_signature": result["search_signature"]},
        )
        assert cleared.status_code == 200
        assert cleared.json()["deleted_count"] == 2

        third = client.post(
            "/api/application-automation/zhaopin/search-import",
            json={"page_limit": 1, "import_limit": 10},
        )
        assert third.status_code == 200
        assert third.json()["history_skipped_count"] == 0
        assert len(third.json()["candidates"]) == 3
        assert "home" in bridge.closed_targets
        assert "search" in bridge.closed_targets
    finally:
        app.dependency_overrides.pop(get_browser_bridge, None)


def test_company_size_preference_does_not_block_an_otherwise_matching_import(client):
    create_search_profile(client)
    client.put("/api/user-profile", json={
        "current_city": "重庆",
        "preferred_cities": ["重庆"],
        "target_roles": ["直播运营"],
        "salary_min": 3000,
        "degree": "大专",
        "experience_level": "应届生/实习生",
        "company_sizes": ["初创公司"],
    })
    bridge = FakeZhaopinSearchBridge()
    app.dependency_overrides[get_browser_bridge] = lambda: bridge
    try:
        response = client.post(
            "/api/application-automation/zhaopin/search-import",
            json={"page_limit": 1, "import_limit": 5},
        )
        assert response.status_code == 200
        result = response.json()
        assert result["created_count"] == 1
        assert "公司规模不符合用户偏好" not in result["candidates"][0]["blockers"]
    finally:
        app.dependency_overrides.pop(get_browser_bridge, None)


def test_manual_search_keyword_is_used_for_this_search_matching(client):
    create_search_profile(client)
    bridge = ManualKeywordSearchBridge()
    app.dependency_overrides[get_browser_bridge] = lambda: bridge
    try:
        response = client.post(
            "/api/application-automation/zhaopin/search-import",
            json={"keyword": "AI漫剧", "page_limit": 1, "import_limit": 10},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["eligible_count"] == 1
        assert result["created_count"] == 1
        assert result["candidates"][0]["title"] == "AI漫剧制作师（实习生）"
        assert result["candidates"][0]["import_action"] == "created"
        assert client.get("/api/user-profile").json()["target_roles"] == ["直播运营"]
    finally:
        app.dependency_overrides.pop(get_browser_bridge, None)


def test_one_click_run_searches_imports_blacklists_and_queues_with_greeting(client):
    create_search_profile(client)
    resume = client.post(
        "/api/resumes",
        json={
            "title": "直播运营主简历",
            "target_role": "直播运营",
            "status": "ready",
            "is_primary": True,
            "content": "直播运营、场控协助和数据复盘经验",
        },
    )
    assert resume.status_code == 201
    bridge = FakeZhaopinSearchBridge()
    app.dependency_overrides[get_browser_bridge] = lambda: bridge
    try:
        response = client.post(
            "/api/application-automation/auto-apply/run",
            json={
                "page_limit": 1,
                "import_limit": 10,
                "greeting_content": "您好，我已投递简历，期待进一步沟通。",
            },
        )

        assert response.status_code == 200
        result = response.json()
        assert result["search"]["scanned_count"] == 3
        assert result["search"]["eligible_count"] == 1
        assert result["search"]["created_count"] == 1
        assert result["search"]["auto_blacklisted_count"] == 1
        assert result["plan"]["eligible_count"] == 1
        assert result["plan"]["queued_count"] == 1

        tasks = client.get("/api/application-automation/tasks").json()
        assert len(tasks) == 1
        assert tasks[0]["status"] == "draft"
        assert tasks[0]["greeting_snapshot"] == "您好，我已投递简历，期待进一步沟通。"

        blacklist = client.get("/api/blacklist").json()
        assert [rule["company_name"] for rule in blacklist] == ["重庆零薪传媒有限公司"]
    finally:
        app.dependency_overrides.pop(get_browser_bridge, None)
