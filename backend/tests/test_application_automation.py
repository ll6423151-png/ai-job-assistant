from app.main import app
from app.api.routes import application_automation as automation_routes
from app.services.browser_bridge import BrowserBridgeError, get_browser_bridge


class FakeBrowserBridge:
    def __init__(self) -> None:
        self.clicked = False

    def is_available(self) -> bool:
        return True

    def list_targets(self):
        return [{"id": "zhaopin-tab", "url": "https://www.zhaopin.com/jobdetail/test.htm"}]

    def find_target_for_hosts(self, hosts):
        return "zhaopin-tab"

    def open_url(self, url: str) -> str:
        return "zhaopin-tab"

    def evaluate(self, target_id: str, script: str):
        if "element.click()" in script:
            self.clicked = True
            return {"clicked": True, "text": "立即投递"}
        body = "智联招聘 岗位详情"
        return {
            "url": "https://www.zhaopin.com/jobdetail/test.htm",
            "title": "短视频运营实习生",
            "body_text": body,
            "apply_controls": [{"text": "立即投递"}],
        }


class NoOpenPlatformPageBridge(FakeBrowserBridge):
    def find_target_for_hosts(self, hosts):
        return None


class DirectSuccessBrowserBridge(FakeBrowserBridge):
    def evaluate(self, target_id: str, script: str):
        if "element.click()" in script:
            self.clicked = True
            return {"clicked": True, "text": "立即投递"}
        if not self.clicked:
            return super().evaluate(target_id, script)
        return {
            "url": "https://www.zhaopin.com/jobdetail/success.htm",
            "title": "直播运营助理",
            "body_text": "职位详情 已投递",
            "apply_controls": [],
        }


class ResumeDialogBrowserBridge(FakeBrowserBridge):
    def __init__(self) -> None:
        super().__init__()
        self.entry_clicked = False
        self.resume_selected = False
        self.delivered = False

    def evaluate(self, target_id: str, script: str):
        if "a-job-apply-resume-selection-panel__deliver" in script:
            self.delivered = True
            return {"clicked": True, "text": "立即申请"}
        if "a-job-apply-resume-selection-panel" in script and "visible" in script:
            return {
                "visible": self.entry_clicked and not self.delivered,
                "selected_label": "默认简历",
                "resume_options": ["默认简历", "运营简历"],
            }
        if "a-selector-option" in script:
            self.resume_selected = True
            return {"selected": True, "selected_text": "运营简历"}
        if "element.click()" in script:
            self.entry_clicked = True
            return {"clicked": True, "text": "立即投递"}
        if self.delivered:
            return {
                "url": "https://www.zhaopin.com/jobdetail/dialog-success.htm",
                "title": "直播运营助理",
                "body_text": "投递成功",
                "apply_controls": [],
            }
        return super().evaluate(target_id, script)


class PostApplyMessageBrowserBridge(DirectSuccessBrowserBridge):
    def __init__(self) -> None:
        super().__init__()
        self.communication_opened = False
        self.message_sent = False

    def evaluate(self, target_id: str, script: str):
        if "post-apply-communication-open" in script:
            self.communication_opened = True
            return {"clicked": True, "text": "立即沟通"}
        if "post-apply-communication-send" in script:
            self.message_sent = True
            return {
                "status": "sent",
                "sent": True,
                "evidence": "message_input_cleared",
            }
        return super().evaluate(target_id, script)


class AppOnlyMessageBrowserBridge(DirectSuccessBrowserBridge):
    def evaluate(self, target_id: str, script: str):
        if "post-apply-communication-open" in script:
            return {"clicked": True, "text": "立即沟通"}
        if "post-apply-communication-send" in script:
            return {
                "status": "manual_required",
                "sent": False,
                "reason": "智联 PC 网页仅提供 APP 下载提示，没有消息输入框",
            }
        return super().evaluate(target_id, script)


class MessageBridgeFailureAfterApply(DirectSuccessBrowserBridge):
    def evaluate(self, target_id: str, script: str):
        if "post-apply-communication-open" in script:
            raise BrowserBridgeError("沟通入口读取失败")
        return super().evaluate(target_id, script)


def test_only_zhaopin_recruitment_adapter_is_enabled(client):
    adapters = client.get("/api/platform-adapters").json()
    recruitment_adapters = [
        adapter
        for adapter in adapters
        if adapter["key"] != "manual_import"
    ]

    assert [adapter["key"] for adapter in recruitment_adapters] == ["zhaopin"]
    adapter = recruitment_adapters[0]
    assert "resume_selection" not in adapter["capabilities"]
    assert "confirmed_application_entry_click" in adapter["capabilities"]
    assert "post_click_page_capture" in adapter["capabilities"]

    automation_platforms = client.get("/api/application-automation/platforms").json()
    assert [platform["key"] for platform in automation_platforms] == ["zhaopin"]
    assert "post_apply_communication_attempt" in automation_platforms[0]["capabilities"]


def test_missing_zhaopin_page_is_unknown_instead_of_logged_out(client):
    bridge = NoOpenPlatformPageBridge()
    app.dependency_overrides[get_browser_bridge] = lambda: bridge
    try:
        response = client.get("/api/application-automation/platforms/zhaopin/login-status")
        assert response.status_code == 200
        assert response.json()["status"] == "unknown"
        assert "未打开" in response.json()["message"]
        assert "搜索" in response.json()["message"]
    finally:
        app.dependency_overrides.pop(get_browser_bridge, None)


def create_automation_resume(client):
    return client.post(
        "/api/resumes",
        json={"title": "运营简历", "content": "短视频运营和数据复盘经验"},
    ).json()


def create_automation_job(client, suffix: str):
    return client.post(
        "/api/jobs",
        json={
            "title": f"短视频运营实习生 {suffix}",
            "company_name": "测试公司",
            "salary_min": 4000,
            "source_url": f"https://www.zhaopin.com/jobdetail/{suffix}.htm",
        },
    ).json()


def create_and_prepare_task(client, job_id: int, resume_id: int):
    created = client.post(
        "/api/application-automation/tasks",
        json={
            "platform_key": "zhaopin",
            "job_id": job_id,
            "resume_id": resume_id,
        },
    )
    assert created.status_code == 201
    task_id = created.json()["id"]
    prepared = client.post(f"/api/application-automation/tasks/{task_id}/prepare")
    assert prepared.status_code == 200
    assert prepared.json()["status"] == "awaiting_confirmation"
    return prepared.json()


def submit_prepared_task(client, task: dict):
    return client.post(
        f"/api/application-automation/tasks/{task['id']}/submit",
        json={
            "confirmed": True,
            "confirmation_token": task["confirmation_token"],
        },
    )


def test_duplicate_job_task_is_rejected(client):
    resume = create_automation_resume(client)
    job = create_automation_job(client, "duplicate")
    payload = {
        "platform_key": "zhaopin",
        "job_id": job["id"],
        "resume_id": resume["id"],
    }

    first = client.post("/api/application-automation/tasks", json=payload)
    duplicate = client.post("/api/application-automation/tasks", json=payload)

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert "重复" in duplicate.json()["detail"]


def test_task_keeps_user_entered_greeting_snapshot(client):
    resume = create_automation_resume(client)
    job = create_automation_job(client, "custom-greeting")

    response = client.post(
        "/api/application-automation/tasks",
        json={
            "platform_key": "zhaopin",
            "job_id": job["id"],
            "resume_id": resume["id"],
            "greeting_content": "您好，我对直播运营助理岗位感兴趣。",
        },
    )

    assert response.status_code == 201
    assert response.json()["greeting_id"] is None
    assert response.json()["greeting_snapshot"] == "您好，我对直播运营助理岗位感兴趣。"


def test_daily_submission_limit_blocks_next_external_attempt(client, monkeypatch):
    monkeypatch.setattr(automation_routes.settings, "application_automation_daily_limit", 1)
    monkeypatch.setattr(automation_routes.settings, "application_automation_cooldown_seconds", 0)
    bridge = FakeBrowserBridge()
    app.dependency_overrides[get_browser_bridge] = lambda: bridge
    try:
        resume = create_automation_resume(client)
        first_task = create_and_prepare_task(
            client,
            create_automation_job(client, "daily-first")["id"],
            resume["id"],
        )
        second_task = create_and_prepare_task(
            client,
            create_automation_job(client, "daily-second")["id"],
            resume["id"],
        )

        assert submit_prepared_task(client, first_task).status_code == 200
        limited = submit_prepared_task(client, second_task)

        assert limited.status_code == 429
        assert "每日" in limited.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_browser_bridge, None)


def test_submission_cooldown_blocks_immediate_next_attempt(client, monkeypatch):
    monkeypatch.setattr(automation_routes.settings, "application_automation_daily_limit", 20)
    monkeypatch.setattr(automation_routes.settings, "application_automation_cooldown_seconds", 60)
    bridge = FakeBrowserBridge()
    app.dependency_overrides[get_browser_bridge] = lambda: bridge
    try:
        resume = create_automation_resume(client)
        first_task = create_and_prepare_task(
            client,
            create_automation_job(client, "cooldown-first")["id"],
            resume["id"],
        )
        second_task = create_and_prepare_task(
            client,
            create_automation_job(client, "cooldown-second")["id"],
            resume["id"],
        )

        assert submit_prepared_task(client, first_task).status_code == 200
        cooling_down = submit_prepared_task(client, second_task)

        assert cooling_down.status_code == 429
        assert "冷却" in cooling_down.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_browser_bridge, None)


def test_confirmed_zhaopin_click_creates_manual_verification_record(client):
    bridge = FakeBrowserBridge()
    app.dependency_overrides[get_browser_bridge] = lambda: bridge
    try:
        resume = client.post(
            "/api/resumes",
            json={"title": "运营简历", "content": "短视频运营和数据复盘经验"},
        ).json()
        job = client.post(
            "/api/jobs",
            json={
                "title": "短视频运营实习生",
                "company_name": "测试公司",
                "description": "负责短视频账号运营",
                "salary_min": 4000,
                "salary_max": 8000,
                "source_url": "https://www.zhaopin.com/jobdetail/test.htm",
                "source_platform": "智联招聘",
            },
        ).json()
        created = client.post(
            "/api/application-automation/tasks",
            json={
                "platform_key": "zhaopin",
                "job_id": job["id"],
                "resume_id": resume["id"],
            },
        )
        assert created.status_code == 201
        task_id = created.json()["id"]

        prepared = client.post(f"/api/application-automation/tasks/{task_id}/prepare")
        assert prepared.status_code == 200
        assert prepared.json()["status"] == "awaiting_confirmation"
        token = prepared.json()["confirmation_token"]

        submitted = client.post(
            f"/api/application-automation/tasks/{task_id}/submit",
            json={"confirmed": True, "confirmation_token": token},
        )
        assert submitted.status_code == 200
        result = submitted.json()
        assert result["status"] == "verification_required"
        assert result["external_result"]["verified"] is False
        assert result["application_record_id"] is not None

        applications = client.get("/api/applications").json()
        assert len(applications) == 1
        assert applications[0]["status"] == "prepared"
        assert applications[0]["channel"] == "zhaopin"

        duplicate = client.post(
            f"/api/application-automation/tasks/{task_id}/submit",
            json={"confirmed": True, "confirmation_token": token},
        )
        assert duplicate.status_code == 409
        assert len(client.get("/api/applications").json()) == 1
    finally:
        app.dependency_overrides.pop(get_browser_bridge, None)


def test_automation_rejects_blacklisted_and_low_salary_jobs(client):
    resume = client.post(
        "/api/resumes",
        json={"title": "运营简历", "content": "短视频运营经验"},
    ).json()
    client.post(
        "/api/blacklist",
        json={
            "company_name": "敏思跃动",
            "match_type": "exact",
            "reason": "用户要求屏蔽",
            "is_active": True,
        },
    )
    blocked_job = client.post(
        "/api/jobs",
        json={
            "title": "新媒体运营实习生",
            "company_name": "敏思跃动",
            "salary_min": 5000,
            "source_url": "https://www.zhaopin.com/jobdetail/blocked.htm",
        },
    ).json()
    blocked = client.post(
        "/api/application-automation/tasks",
        json={"platform_key": "zhaopin", "job_id": blocked_job["id"], "resume_id": resume["id"]},
    )
    assert blocked.status_code == 409

    low_salary_job = client.post(
        "/api/jobs",
        json={
            "title": "短视频运营实习生",
            "company_name": "其他公司",
            "salary_min": 2500,
            "source_url": "https://www.zhaopin.com/jobdetail/low.htm",
        },
    ).json()
    low_salary = client.post(
        "/api/application-automation/tasks",
        json={"platform_key": "zhaopin", "job_id": low_salary_job["id"], "resume_id": resume["id"]},
    )
    assert low_salary.status_code == 422


def test_zero_salary_job_automatically_blacklists_company(client):
    resume = create_automation_resume(client)
    job = client.post(
        "/api/jobs",
        json={
            "title": "零薪运营实习生",
            "company_name": "零薪测试公司",
            "salary_min": 0,
            "salary_max": 0,
            "source_url": "https://www.zhaopin.com/jobdetail/zero-salary.htm",
        },
    ).json()

    response = client.post(
        "/api/application-automation/tasks",
        json={
            "platform_key": "zhaopin",
            "job_id": job["id"],
            "resume_id": resume["id"],
        },
    )

    assert response.status_code == 409
    assert "黑名单" in response.json()["detail"]
    rules = client.get("/api/blacklist").json()
    assert len(rules) == 1
    assert rules[0]["company_name"] == "零薪测试公司"
    assert "0" in rules[0]["reason"]


def test_automation_keeps_3000_hard_floor_when_profile_is_lower(client):
    client.put("/api/user-profile", json={"salary_min": 1000})
    resume = client.post(
        "/api/resumes",
        json={"title": "运营简历", "content": "短视频运营经验"},
    ).json()
    job = client.post(
        "/api/jobs",
        json={
            "title": "短视频运营实习生",
            "company_name": "其他公司",
            "salary_min": 2500,
            "source_url": "https://www.zhaopin.com/jobdetail/hard-floor.htm",
        },
    ).json()

    response = client.post(
        "/api/application-automation/tasks",
        json={
            "platform_key": "zhaopin",
            "job_id": job["id"],
            "resume_id": resume["id"],
        },
    )

    assert response.status_code == 422
    assert "3000" in response.json()["detail"]


def test_automation_respects_profile_floor_above_3000(client):
    client.put("/api/user-profile", json={"salary_min": 5000})
    resume = client.post(
        "/api/resumes",
        json={"title": "运营简历", "content": "短视频运营经验"},
    ).json()
    job = client.post(
        "/api/jobs",
        json={
            "title": "短视频运营实习生",
            "company_name": "其他公司",
            "salary_min": 4000,
            "source_url": "https://www.zhaopin.com/jobdetail/profile-floor.htm",
        },
    ).json()

    response = client.post(
        "/api/application-automation/tasks",
        json={
            "platform_key": "zhaopin",
            "job_id": job["id"],
            "resume_id": resume["id"],
        },
    )

    assert response.status_code == 422
    assert "5000" in response.json()["detail"]


def test_job_keyword_blocks_matching_application_without_polluting_company_blacklist(client):
    keyword = client.post("/api/job-keywords", json={"keyword": "主播", "is_active": True})
    assert keyword.status_code == 201
    assert keyword.json()["keyword"] == "主播"
    assert client.get("/api/blacklist").json() == []

    resume = create_automation_resume(client)
    blocked_job = client.post(
        "/api/jobs",
        json={
            "title": "海外主播",
            "company_name": "正常测试公司",
            "city": "重庆",
            "salary_min": 6000,
            "description": "负责直播和账号运营",
            "source_platform": "智联招聘",
            "source_url": "https://www.zhaopin.com/jobdetail/blocked-keyword.htm",
        },
    ).json()
    response = client.post(
        "/api/application-automation/tasks",
        json={"platform_key": "zhaopin", "job_id": blocked_job["id"], "resume_id": resume["id"]},
    )
    assert response.status_code == 409
    assert "主播" in response.json()["detail"]

    deleted = client.delete(f"/api/job-keywords/{keyword.json()['id']}")
    assert deleted.status_code == 204


def test_auto_apply_plan_queues_only_profile_compatible_jobs_and_can_cancel(client):
    profile = client.put(
        "/api/user-profile",
        json={
            "preferred_cities": ["Chongqing"],
            "target_roles": ["Operations"],
            "salary_min": 3000,
            "degree": "大专",
            "experience_level": "应届生/实习生",
            "company_sizes": ["中小企业"],
        },
    )
    assert profile.status_code == 200
    resume = client.post(
        "/api/resumes",
        json={
            "title": "Primary Resume",
            "target_role": "Operations",
            "status": "ready",
            "is_primary": True,
            "content": "Operations internship experience",
        },
    )
    assert resume.status_code == 201
    eligible = client.post(
        "/api/jobs",
        json={
            "title": "Operations Assistant",
            "company_name": "Chongqing Media",
            "city": "Chongqing",
            "salary_min": 4000,
            "salary_max": 7000,
            "degree_required": "大专",
            "experience_required": "接受实习",
            "company_size": "中小企业",
            "description": "Operations and live content",
            "source_platform": "智联招聘",
            "source_url": "https://www.zhaopin.com/jobdetail/plan-eligible.htm",
        },
    )
    assert eligible.status_code == 201
    blocked = client.post(
        "/api/jobs",
        json={
            "title": "Operations Assistant",
            "company_name": "Shenzhen Media",
            "city": "Shenzhen",
            "salary_min": 4000,
            "source_platform": "智联招聘",
            "source_url": "https://www.zhaopin.com/jobdetail/plan-blocked.htm",
        },
    )
    assert blocked.status_code == 201

    plan = client.post(
        "/api/application-automation/auto-apply/plan",
        json={"greeting_content": "您好，我已投递简历，期待进一步沟通。"},
    )

    assert plan.status_code == 200
    data = plan.json()
    assert data["resume_id"] == resume.json()["id"]
    assert data["eligible_count"] == 1
    assert data["queued_count"] == 1
    eligible_candidate = next(item for item in data["candidates"] if item["eligible"])
    blocked_candidate = next(item for item in data["candidates"] if not item["eligible"])
    assert eligible_candidate["task_status"] == "draft"
    assert "城市" in "".join(blocked_candidate["blockers"])
    task = next(
        item
        for item in client.get("/api/application-automation/tasks").json()
        if item["id"] == eligible_candidate["task_id"]
    )
    assert task["greeting_snapshot"] == "您好，我已投递简历，期待进一步沟通。"

    updated_plan = client.post(
        "/api/application-automation/auto-apply/plan",
        json={"greeting_content": "您好，简历已经投递，期待与您沟通岗位细节。"},
    )
    assert updated_plan.status_code == 200
    assert updated_plan.json()["queued_count"] == 0
    updated_task = next(
        item
        for item in client.get("/api/application-automation/tasks").json()
        if item["id"] == eligible_candidate["task_id"]
    )
    assert updated_task["greeting_snapshot"] == "您好，简历已经投递，期待与您沟通岗位细节。"

    cancelled = client.post(
        f"/api/application-automation/tasks/{eligible_candidate['task_id']}/cancel",
        json={"reason": "用户选择不投递"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_auto_apply_plan_requires_core_profile_fields(client):
    client.put("/api/user-profile", json={"salary_min": 3000})
    client.post(
        "/api/resumes",
        json={
            "title": "Primary Resume",
            "status": "ready",
            "is_primary": True,
            "content": "Operations experience",
        },
    )

    response = client.post("/api/application-automation/auto-apply/plan")

    assert response.status_code == 409
    assert "目标岗位" in response.json()["detail"]
    assert "求职城市" in response.json()["detail"]


def test_zhaopin_direct_apply_success_marker_is_verified(client, monkeypatch):
    monkeypatch.setattr(automation_routes.settings, "application_automation_cooldown_seconds", 0)
    bridge = DirectSuccessBrowserBridge()
    app.dependency_overrides[get_browser_bridge] = lambda: bridge
    try:
        resume = create_automation_resume(client)
        job = create_automation_job(client, "success")
        prepared = create_and_prepare_task(client, job["id"], resume["id"])

        submitted = submit_prepared_task(client, prepared)

        assert submitted.status_code == 200
        result = submitted.json()
        assert result["status"] == "submitted", result
        assert result["external_result"]["verified"] is True
        assert "已投递" in result["external_result"]["success_evidence"]
    finally:
        app.dependency_overrides.pop(get_browser_bridge, None)


def test_zhaopin_resume_dialog_selects_named_resume_before_delivery(client, monkeypatch):
    monkeypatch.setattr(automation_routes.settings, "application_automation_cooldown_seconds", 0)
    bridge = ResumeDialogBrowserBridge()
    app.dependency_overrides[get_browser_bridge] = lambda: bridge
    try:
        resume = client.post(
            "/api/resumes",
            json={"title": "运营简历", "content": "直播运营经验"},
        ).json()
        job = create_automation_job(client, "dialog-success")
        prepared = create_and_prepare_task(client, job["id"], resume["id"])

        submitted = submit_prepared_task(client, prepared)

        assert submitted.status_code == 200
        result = submitted.json()
        assert result["status"] == "submitted", result
        assert result["external_result"]["resume_selection"]["selected"] is True
        assert result["external_result"]["resume_selection"]["selected_text"] == "运营简历"
        assert bridge.resume_selected is True
        assert bridge.delivered is True
    finally:
        app.dependency_overrides.pop(get_browser_bridge, None)


def test_zhaopin_sends_greeting_after_verified_application(client, monkeypatch):
    monkeypatch.setattr(automation_routes.settings, "application_automation_cooldown_seconds", 0)
    bridge = PostApplyMessageBrowserBridge()
    app.dependency_overrides[get_browser_bridge] = lambda: bridge
    try:
        resume = create_automation_resume(client)
        job = create_automation_job(client, "greeting-send")
        created = client.post(
            "/api/application-automation/tasks",
            json={
                "platform_key": "zhaopin",
                "job_id": job["id"],
                "resume_id": resume["id"],
                "greeting_content": "您好，我想申请该岗位。",
            },
        ).json()
        prepared = client.post(
            f"/api/application-automation/tasks/{created['id']}/prepare"
        ).json()

        response = client.post(
            f"/api/application-automation/tasks/{created['id']}/submit",
            json={
                "confirmed": True,
                "confirmation_token": prepared["confirmation_token"],
            },
        )

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "submitted"
        assert result["external_result"]["communication"]["status"] == "sent"
        assert result["external_result"]["communication"]["sent"] is True
        assert bridge.communication_opened is True
        assert bridge.message_sent is True
    finally:
        app.dependency_overrides.pop(get_browser_bridge, None)


def test_zhaopin_records_manual_message_when_pc_web_has_no_input(client, monkeypatch):
    monkeypatch.setattr(automation_routes.settings, "application_automation_cooldown_seconds", 0)
    bridge = AppOnlyMessageBrowserBridge()
    app.dependency_overrides[get_browser_bridge] = lambda: bridge
    try:
        resume = create_automation_resume(client)
        job = create_automation_job(client, "greeting-app-only")
        created = client.post(
            "/api/application-automation/tasks",
            json={
                "platform_key": "zhaopin",
                "job_id": job["id"],
                "resume_id": resume["id"],
                "greeting_content": "您好，我已投递简历，期待进一步沟通。",
            },
        ).json()
        prepared = client.post(
            f"/api/application-automation/tasks/{created['id']}/prepare"
        ).json()

        response = client.post(
            f"/api/application-automation/tasks/{created['id']}/submit",
            json={
                "confirmed": True,
                "confirmation_token": prepared["confirmation_token"],
            },
        )

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "submitted"
        communication = result["external_result"]["communication"]
        assert communication["status"] == "manual_required"
        assert communication["sent"] is False
        assert "APP" in communication["reason"]
        assert "APP" in result["error_message"]
    finally:
        app.dependency_overrides.pop(get_browser_bridge, None)


def test_message_bridge_failure_does_not_erase_verified_application(client, monkeypatch):
    monkeypatch.setattr(automation_routes.settings, "application_automation_cooldown_seconds", 0)
    bridge = MessageBridgeFailureAfterApply()
    app.dependency_overrides[get_browser_bridge] = lambda: bridge
    try:
        resume = create_automation_resume(client)
        job = create_automation_job(client, "message-bridge-failure")
        created = client.post(
            "/api/application-automation/tasks",
            json={
                "platform_key": "zhaopin",
                "job_id": job["id"],
                "resume_id": resume["id"],
                "greeting_content": "您好，我已投递简历，期待进一步沟通。",
            },
        ).json()
        prepared = client.post(
            f"/api/application-automation/tasks/{created['id']}/prepare"
        ).json()

        response = submit_prepared_task(client, prepared)

        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "submitted"
        assert result["application_record_id"] is not None
        communication = result["external_result"]["communication"]
        assert communication["status"] == "manual_required"
        assert "沟通入口读取失败" in communication["reason"]
    finally:
        app.dependency_overrides.pop(get_browser_bridge, None)
