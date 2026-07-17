from app.platforms.base import PlatformAdapter
from app.schemas.job import JobCreate


class RecruitmentPlatformAdapter(PlatformAdapter):
    supports_application_submit = True
    capabilities = (
        "manual_login_session",
        "job_page_preview",
        "confirmed_application_entry_click",
        "success_marker_check",
    )

    def normalize_job(self, payload: JobCreate) -> JobCreate:
        data = payload.model_dump()
        data["source_platform"] = self.name
        return JobCreate(**data)


class ZhaopinAdapter(RecruitmentPlatformAdapter):
    key = "zhaopin"
    name = "智联招聘"
    description = "复用用户手动登录的智联招聘会话，确认后点击单条“立即投递”入口并保留点击后页面快照。"
    capabilities = (
        "manual_login_session",
        "profile_based_job_search",
        "confirmed_job_import",
        "job_page_preview",
        "confirmed_application_entry_click",
        "conditional_resume_selection",
        "direct_apply_default_resume",
        "post_click_page_capture",
        "post_apply_communication_attempt",
        "success_marker_check",
    )
    login_url = "https://www.zhaopin.com/"
    allowed_hosts = ("zhaopin.com", "www.zhaopin.com")
    apply_labels = ("立即投递",)
    confirmation_labels = ("确定投递", "投递简历", "继续投递")
    success_markers = ("已投递", "投递成功")
    logged_in_markers = ("我的投递", "个人中心", "退出")
    logged_out_markers = ("登录/注册", "验证码登录/注册", "获取验证码")
