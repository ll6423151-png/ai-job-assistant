from datetime import datetime, time, timezone
from math import ceil
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.db.session import get_db
from app.models.application_automation import AutomatedApplicationTask
from app.models.greeting_message import GreetingMessage
from app.models.job import Job
from app.models.job_search_exclusion import JobSearchExclusion
from app.models.resume import Resume
from app.models.user_profile import UserProfile
from app.platforms import adapter_registry
from app.platforms.base import PlatformAdapter
from app.schemas.application_automation import AutoApplyCandidateRead, AutoApplyPlanRead, AutoApplyPlanRequest, AutoApplyRunRead, AutoApplyRunRequest, AutomationPlatformInfo, AutomationCancelRequest, AutomationSubmitRequest, AutomationTaskCreate, AutomationTaskRead, LoginStatus, ZhaopinSearchCandidateRead, ZhaopinSearchExclusionClearRead, ZhaopinSearchExclusionClearRequest, ZhaopinSearchImportRead, ZhaopinSearchImportRequest
from app.services.auto_apply import evaluate_job
from app.services.job_keywords import active_job_keywords, matched_job_keyword
from app.services.job_search_history import build_search_signature
from app.services.zhaopin_search import canonical_job_url, is_zero_or_unpaid_salary, load_job_description, search_jobs
from app.services.application_automation import detect_login_status, ensure_company_blacklisted, find_blacklist_match, inspect_page, prepare_task, submit_task, validate_platform_url
from app.services.browser_bridge import BrowserBridge, BrowserBridgeError, get_browser_bridge
router = APIRouter()
SUPPORTED_PLATFORMS = {'zhaopin'}
HARD_MINIMUM_SALARY = 3000
DUPLICATE_BLOCKING_STATUSES = {'draft', 'awaiting_login', 'awaiting_confirmation', 'submitting', 'submitted', 'verification_required'}
SUBMISSION_ATTEMPT_STATUSES = {'submitting', 'submitted', 'verification_required', 'failed'}

def require_platform(key: str) -> PlatformAdapter:
    adapter = adapter_registry.get(key)
    if adapter is None or key not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=404, detail='不支持该招聘平台')
    return adapter

async def require_task(db: AsyncSession, task_id: int) -> AutomatedApplicationTask:
    task = await db.get(AutomatedApplicationTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail='投递任务不存在')
    return task

def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

async def enforce_submission_policy(db: AsyncSession, task: AutomatedApplicationTask) -> None:
    now = datetime.now(timezone.utc)
    day_start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    attempt_count = await db.scalar(select(func.count()).select_from(AutomatedApplicationTask).where(AutomatedApplicationTask.status.in_(SUBMISSION_ATTEMPT_STATUSES), AutomatedApplicationTask.submitted_at.is_not(None), AutomatedApplicationTask.submitted_at >= day_start)) or 0
    if attempt_count >= settings.application_automation_daily_limit:
        raise HTTPException(status_code=429, detail=f'已达到每日外部投递尝试上限 {settings.application_automation_daily_limit} 次，请明日再试')
    latest_attempt = await db.scalar(select(AutomatedApplicationTask).where(AutomatedApplicationTask.id != task.id, AutomatedApplicationTask.status.in_(SUBMISSION_ATTEMPT_STATUSES), AutomatedApplicationTask.submitted_at.is_not(None)).order_by(desc(AutomatedApplicationTask.submitted_at)).limit(1))
    if latest_attempt and latest_attempt.submitted_at:
        elapsed = (now - as_utc(latest_attempt.submitted_at)).total_seconds()
        remaining = settings.application_automation_cooldown_seconds - elapsed
        if remaining > 0:
            raise HTTPException(status_code=429, detail=f'外部投递仍在冷却期，请等待 {ceil(remaining)} 秒后重试')

@router.get('/application-automation/platforms', response_model=list[AutomationPlatformInfo])
def list_platforms(bridge: BrowserBridge=Depends(get_browser_bridge)) -> list[AutomationPlatformInfo]:
    available = bridge.is_available()
    platforms: list[AutomationPlatformInfo] = []
    for key in ('zhaopin',):
        adapter = require_platform(key)
        platforms.append(AutomationPlatformInfo(key=key, name=adapter.name, description=adapter.description, login_url=adapter.login_url, capabilities=list(adapter.capabilities), browser_bridge_available=available, daily_submission_limit=settings.application_automation_daily_limit, cooldown_seconds=settings.application_automation_cooldown_seconds))
    return platforms

@router.post('/application-automation/platforms/{platform_key}/open-login', response_model=LoginStatus)
def open_login(platform_key: str, bridge: BrowserBridge=Depends(get_browser_bridge)) -> LoginStatus:
    adapter = require_platform(platform_key)
    try:
        target_id = bridge.open_url(adapter.login_url)
    except BrowserBridgeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return LoginStatus(platform_key=platform_key, status='unknown', target_id=target_id, message=f'已打开{adapter.name}，请手动完成登录或验证码')

@router.get('/application-automation/platforms/{platform_key}/login-status', response_model=LoginStatus)
def check_login(platform_key: str, bridge: BrowserBridge=Depends(get_browser_bridge)) -> LoginStatus:
    adapter = require_platform(platform_key)
    try:
        target_id = bridge.find_target_for_hosts(adapter.allowed_hosts)
        if not target_id:
            return LoginStatus(platform_key=platform_key, status='unknown', message=f'未打开{adapter.name}页面；点击“打开登录”或直接“搜索并生成清单”即可连接')
        page = inspect_page(bridge, target_id, adapter)
        login_status, evidence = detect_login_status(page, adapter)
    except BrowserBridgeError as exc:
        return LoginStatus(platform_key=platform_key, status='bridge_unavailable', message=str(exc))
    return LoginStatus(platform_key=platform_key, status=login_status, target_id=target_id, evidence=evidence, message=f'{adapter.name}登录状态：{login_status}')

@router.get('/application-automation/tasks', response_model=list[AutomationTaskRead])
async def list_tasks(db: AsyncSession=Depends(get_db)) -> list[AutomatedApplicationTask]:
    return list((await db.scalars(select(AutomatedApplicationTask).order_by(desc(AutomatedApplicationTask.updated_at), desc(AutomatedApplicationTask.id)))).all())

def _profile_search_city(profile: UserProfile) -> str:
    if profile.current_city.strip():
        return profile.current_city.strip()
    return next((city.strip() for city in profile.preferred_cities if city.strip()), '')

@router.post('/application-automation/zhaopin/search-import', response_model=ZhaopinSearchImportRead)
async def search_and_import_zhaopin_jobs(payload: ZhaopinSearchImportRequest, db: AsyncSession=Depends(get_db), bridge: BrowserBridge=Depends(get_browser_bridge)) -> ZhaopinSearchImportRead:
    adapter = require_platform('zhaopin')
    profile = await db.scalar(select(UserProfile).limit(1))
    if profile is None:
        raise HTTPException(status_code=409, detail='请先完成用户中心基本信息')
    keyword = (payload.keyword or '').strip() or next((role.strip() for role in profile.target_roles if role.strip()), '')
    city = (payload.city or '').strip() or _profile_search_city(profile)
    if not keyword or not city or profile.salary_min is None:
        raise HTTPException(status_code=409, detail='请先在用户中心填写目标岗位、求职城市和最低期望月薪')
    query = keyword
    search_target_roles = [keyword] if (payload.keyword or '').strip() else None
    blocked_keywords = await active_job_keywords(db)
    search_signature = build_search_signature(profile, keyword=query, city=city, target_roles=search_target_roles, blocked_keywords=blocked_keywords)
    previous_exclusions = list((await db.scalars(select(JobSearchExclusion).where(JobSearchExclusion.search_signature == search_signature))).all())
    exclusions_by_url = {item.source_url: item for item in previous_exclusions}
    new_exclusion_urls: set[str] = set()
    try:
        search_url, found = search_jobs(bridge, query, payload.page_limit, city)
    except BrowserBridgeError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"智联官网搜索需要电脑 Edge/web-access 桥接。请先启动桥接后重试；也可直接打开 https://www.zhaopin.com/ 手动搜索。原因：{exc}",
        ) from exc
    existing_jobs = list((await db.scalars(select(Job))).all())
    existing_by_url = {canonical_job_url(job.source_url): job for job in existing_jobs if job.source_url}
    candidates: list[ZhaopinSearchCandidateRead] = []
    created_count = 0
    updated_count = 0
    imported_count = 0
    detail_count = 0
    eligible_count = 0
    auto_blacklisted_count = 0
    history_skipped_count = 0
    role_blocker = '岗位标题和 JD 未命中目标岗位'
    for item in found:
        canonical_url = canonical_job_url(item.source_url)
        previous_exclusion = exclusions_by_url.get(canonical_url)
        if previous_exclusion is not None:
            previous_exclusion.last_seen_at = datetime.now(timezone.utc)
            history_skipped_count += 1
            continue
        auto_blacklisted = is_zero_or_unpaid_salary(item.salary_text, item.salary_min, item.salary_max)
        if auto_blacklisted:
            reason = f"智联岗位明确标注无薪或 0 元：{item.salary_text or '0 元'}（自动加入）"
            await ensure_company_blacklisted(db, item.company_name, reason)
            auto_blacklisted_count += 1
        blacklisted = auto_blacklisted or await find_blacklist_match(db, item.company_name) is not None
        transient = Job(title=item.title, company_name=item.company_name, city=item.city, salary_min=item.salary_min, salary_max=item.salary_max, degree_required=item.degree_required, experience_required=item.experience_required, company_size=item.company_size, description=item.description, source_platform='智联招聘', source_url=item.source_url, status='open')
        decision = evaluate_job(transient, profile, adapter, blacklisted=blacklisted, target_roles=search_target_roles, blocked_keywords=blocked_keywords)
        description_loaded = False
        job_id: int | None = None
        import_action: str | None = None
        non_role_blockers = [blocker for blocker in decision.blockers if blocker != role_blocker]
        if not non_role_blockers and detail_count < payload.import_limit:
            detail = load_job_description(bridge, item.source_url)
            detail_count += 1
            if detail:
                item.description = detail
                transient.description = detail
                description_loaded = True
                decision = evaluate_job(transient, profile, adapter, blacklisted=blacklisted, target_roles=search_target_roles, blocked_keywords=blocked_keywords)
        if decision.eligible:
            eligible_count += 1
            if imported_count < payload.import_limit:
                existing = existing_by_url.get(canonical_url)
                values = {'title': item.title, 'company_name': item.company_name, 'city': item.city, 'salary_min': item.salary_min, 'salary_max': item.salary_max, 'degree_required': item.degree_required, 'experience_required': item.experience_required, 'company_size': item.company_size, 'description': item.description, 'source_platform': '智联招聘', 'source_url': canonical_url, 'status': 'open', 'is_archived': False}
                if existing is None:
                    existing = Job(**values)
                    db.add(existing)
                    await db.flush()
                    existing_by_url[canonical_url] = existing
                    created_count += 1
                    import_action = 'created'
                else:
                    for field, value in values.items():
                        setattr(existing, field, value)
                    updated_count += 1
                    import_action = 'updated'
                imported_count += 1
                job_id = existing.id
        elif canonical_url and canonical_url not in new_exclusion_urls:
            db.add(JobSearchExclusion(search_signature=search_signature, source_url=canonical_url, title=item.title, company_name=item.company_name, blockers=list(decision.blockers)))
            new_exclusion_urls.add(canonical_url)
        candidates.append(ZhaopinSearchCandidateRead(title=item.title, company_name=item.company_name, city=item.city, salary_text=item.salary_text, salary_min=item.salary_min, salary_max=item.salary_max, degree_required=item.degree_required, experience_required=item.experience_required, company_size=item.company_size, description_loaded=description_loaded, auto_blacklisted=auto_blacklisted, source_url=item.source_url, eligible=decision.eligible, score=decision.score, reasons=decision.reasons, blockers=decision.blockers, job_id=job_id, import_action=import_action))
    await db.commit()
    return ZhaopinSearchImportRead(query=query, search_url=search_url, pages_requested=payload.page_limit, scanned_count=len(found), eligible_count=eligible_count, created_count=created_count, updated_count=updated_count, auto_blacklisted_count=auto_blacklisted_count, history_skipped_count=history_skipped_count, search_signature=search_signature, candidates=candidates, message=f'智联搜索扫描 {len(found)} 个岗位，符合 {eligible_count} 个，新建 {created_count} 个、更新 {updated_count} 个本地岗位，历史跳过 {history_skipped_count} 个，自动拉黑 {auto_blacklisted_count} 家明确无薪公司。')

@router.post('/application-automation/zhaopin/search-exclusions/clear', response_model=ZhaopinSearchExclusionClearRead)
async def clear_zhaopin_search_exclusions(payload: ZhaopinSearchExclusionClearRequest, db: AsyncSession=Depends(get_db)) -> ZhaopinSearchExclusionClearRead:
    records = list((await db.scalars(select(JobSearchExclusion).where(JobSearchExclusion.search_signature == payload.search_signature))).all())
    for record in records:
        await db.delete(record)
    await db.commit()
    return ZhaopinSearchExclusionClearRead(deleted_count=len(records), message=f'已清除当前搜索条件的 {len(records)} 个历史跳过岗位。')

@router.post('/application-automation/auto-apply/plan', response_model=AutoApplyPlanRead)
async def build_auto_apply_plan(payload: AutoApplyPlanRequest | None=None, db: AsyncSession=Depends(get_db)) -> AutoApplyPlanRead:
    """Queue eligible imported Zhaopin jobs as draft tasks without touching the browser."""
    adapter = require_platform('zhaopin')
    profile = await db.scalar(select(UserProfile).limit(1))
    if profile is None:
        raise HTTPException(status_code=409, detail='请先完成用户中心基本信息')
    missing_profile_fields: list[str] = []
    if not profile.target_roles:
        missing_profile_fields.append('目标岗位')
    if not profile.preferred_cities and (not profile.current_city):
        missing_profile_fields.append('求职城市')
    if profile.salary_min is None:
        missing_profile_fields.append('最低期望月薪')
    if missing_profile_fields:
        raise HTTPException(status_code=409, detail=f"请先在用户中心补充：{'、'.join(missing_profile_fields)}")
    resume = await db.scalar(select(Resume).where(Resume.is_primary.is_(True), Resume.status == 'ready'))
    if resume is None:
        raise HTTPException(status_code=409, detail='请先将一份简历设为主简历并标记为可投递')
    jobs = list((await db.scalars(select(Job).where(Job.status == 'open', Job.is_archived.is_(False)).order_by(desc(Job.updated_at), desc(Job.id)))).all())
    existing_tasks = list((await db.scalars(select(AutomatedApplicationTask))).all())
    active_by_job = {task.job_id: task for task in existing_tasks if task.platform_key == 'zhaopin' and task.status in DUPLICATE_BLOCKING_STATUSES}
    candidates: list[AutoApplyCandidateRead] = []
    queued_count = 0
    greeting_content = (payload.greeting_content or '').strip() if payload else ''
    blocked_keywords = await active_job_keywords(db)
    for job in jobs:
        decision = evaluate_job(job, profile, adapter, blacklisted=await find_blacklist_match(db, job.company_name) is not None, blocked_keywords=blocked_keywords)
        existing = active_by_job.get(job.id)
        task_id = existing.id if existing else None
        task_status = existing.status if existing else None
        if decision.eligible and existing is None:
            task = await create_task(AutomationTaskCreate(platform_key='zhaopin', job_id=job.id, resume_id=resume.id, greeting_content=greeting_content or None), db)
            task_id = task.id
            task_status = task.status
            queued_count += 1
        elif decision.eligible and existing is not None and (existing.status == 'draft') and greeting_content and (existing.greeting_snapshot != greeting_content):
            existing.greeting_id = None
            existing.greeting_snapshot = greeting_content
        candidates.append(AutoApplyCandidateRead(job_id=job.id, title=job.title, company_name=job.company_name, city=job.city, salary_min=job.salary_min, salary_max=job.salary_max, source_url=job.source_url, score=decision.score, reasons=decision.reasons, blockers=decision.blockers, eligible=decision.eligible, task_id=task_id, task_status=task_status))
    eligible_count = sum((1 for candidate in candidates if candidate.eligible))
    skipped_count = len(candidates) - eligible_count
    await db.commit()
    return AutoApplyPlanRead(platform_key='zhaopin', resume_id=resume.id, resume_title=resume.title, salary_floor=max(HARD_MINIMUM_SALARY, profile.salary_min or HARD_MINIMUM_SALARY), eligible_count=eligible_count, queued_count=queued_count, skipped_count=skipped_count, candidates=candidates, message=f'已扫描 {len(candidates)} 个已导入岗位，生成 {queued_count} 个待投递任务；外部平台仍需逐条预览和确认。')

@router.post('/application-automation/auto-apply/run', response_model=AutoApplyRunRead)
async def run_auto_apply_search_and_plan(payload: AutoApplyRunRequest, db: AsyncSession=Depends(get_db), bridge: BrowserBridge=Depends(get_browser_bridge)) -> AutoApplyRunRead:
    """Search Zhaopin and queue local drafts in one user-facing operation."""
    profile = await db.scalar(select(UserProfile).limit(1))
    if profile is None:
        raise HTTPException(status_code=409, detail='请先完成用户中心基本信息')
    missing_profile_fields: list[str] = []
    if not profile.target_roles:
        missing_profile_fields.append('目标岗位')
    if not profile.preferred_cities and (not profile.current_city):
        missing_profile_fields.append('求职城市')
    if profile.salary_min is None:
        missing_profile_fields.append('最低期望月薪')
    if missing_profile_fields:
        raise HTTPException(status_code=409, detail=f"请先在用户中心补充：{'、'.join(missing_profile_fields)}")
    resume = await db.scalar(select(Resume).where(Resume.is_primary.is_(True), Resume.status == 'ready'))
    if resume is None:
        raise HTTPException(status_code=409, detail='请先将一份简历设为主简历并标记为可投递')
    search = await search_and_import_zhaopin_jobs(ZhaopinSearchImportRequest(keyword=payload.keyword, city=payload.city, page_limit=payload.page_limit, import_limit=payload.import_limit), db, bridge)
    plan = await build_auto_apply_plan(AutoApplyPlanRequest(greeting_content=payload.greeting_content), db)
    return AutoApplyRunRead(search=search, plan=plan, message=f'{search.message} {plan.message}')

@router.post('/application-automation/tasks', response_model=AutomationTaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(payload: AutomationTaskCreate, db: AsyncSession=Depends(get_db)) -> AutomatedApplicationTask:
    adapter = require_platform(payload.platform_key)
    job = await db.get(Job, payload.job_id)
    if job is None or job.is_archived:
        raise HTTPException(status_code=404, detail='职位不存在')
    blocked_keyword = matched_job_keyword(job.title, job.description, await active_job_keywords(db))
    if blocked_keyword:
        raise HTTPException(status_code=409, detail=f'岗位命中屏蔽关键词：{blocked_keyword}')
    duplicate = await db.scalar(select(AutomatedApplicationTask).where(AutomatedApplicationTask.platform_key == payload.platform_key, AutomatedApplicationTask.job_id == job.id, AutomatedApplicationTask.status.in_(DUPLICATE_BLOCKING_STATUSES)))
    if duplicate:
        raise HTTPException(status_code=409, detail=f'该平台和岗位已存在投递任务 #{duplicate.id}，请勿重复创建')
    blacklist_rule = await find_blacklist_match(db, job.company_name)
    if blacklist_rule:
        raise HTTPException(status_code=409, detail=f'公司已被黑名单规则拦截：{blacklist_rule.reason or blacklist_rule.company_name}')
    profile = await db.scalar(select(UserProfile).limit(1))
    profile_salary_floor = profile.salary_min if profile and profile.salary_min is not None else HARD_MINIMUM_SALARY
    salary_floor = max(HARD_MINIMUM_SALARY, profile_salary_floor)
    if job.salary_min is not None and job.salary_min <= 0:
        reason = '岗位最低月薪为 0 元（创建投递任务时自动加入）'
        rule = await ensure_company_blacklisted(db, job.company_name, reason)
        await db.commit()
        if rule is not None:
            raise HTTPException(status_code=409, detail=f'岗位薪资为 0 元，公司已自动加入黑名单：{rule.company_name}')
    if job.salary_min is None:
        raise HTTPException(status_code=422, detail=f'岗位未提供可确认的最低月薪，当前只允许月薪下限不低于 {salary_floor} 元的岗位')
    if job.salary_min < salary_floor:
        raise HTTPException(status_code=422, detail=f'岗位月薪下限 {job.salary_min} 元，低于当前最低要求 {salary_floor} 元')
    if not job.source_url or not validate_platform_url(job.source_url, adapter):
        raise HTTPException(status_code=422, detail=f'职位必须填写有效的{adapter.name}链接')
    resume = await db.get(Resume, payload.resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail='简历不存在')
    custom_greeting = (payload.greeting_content or '').strip()
    if payload.greeting_id and custom_greeting:
        raise HTTPException(status_code=400, detail='已审核沟通内容和自定义沟通内容只能选择一种')
    greeting_text = ''
    if payload.greeting_id:
        greeting = await db.get(GreetingMessage, payload.greeting_id)
        if greeting is None:
            raise HTTPException(status_code=404, detail='沟通内容不存在')
        if greeting.status != 'approved':
            raise HTTPException(status_code=409, detail='沟通内容必须先审核通过')
        if greeting.job_id != job.id or greeting.resume_id != resume.id:
            raise HTTPException(status_code=400, detail='沟通内容与所选职位或简历不一致')
        greeting_text = greeting.content
    elif custom_greeting:
        greeting_text = custom_greeting
    task = AutomatedApplicationTask(platform_key=payload.platform_key, job_id=job.id, resume_id=resume.id, greeting_id=payload.greeting_id, job_title_snapshot=job.title, company_snapshot=job.company_name, job_url_snapshot=job.source_url, resume_title_snapshot=resume.title, resume_content_snapshot=resume.content, greeting_snapshot=greeting_text)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task

@router.post('/application-automation/tasks/{task_id}/prepare', response_model=AutomationTaskRead)
async def prepare(task_id: int, db: AsyncSession=Depends(get_db), bridge: BrowserBridge=Depends(get_browser_bridge)) -> AutomatedApplicationTask:
    task = await require_task(db, task_id)
    adapter = require_platform(task.platform_key)
    return await prepare_task(db, task, adapter, bridge)

@router.post('/application-automation/tasks/{task_id}/cancel', response_model=AutomationTaskRead)
async def cancel_task(task_id: int, payload: AutomationCancelRequest, db: AsyncSession=Depends(get_db)) -> AutomatedApplicationTask:
    task = await require_task(db, task_id)
    if task.status in {'submitting', 'submitted', 'verification_required'}:
        raise HTTPException(status_code=409, detail='已进入外部投递流程的任务不能取消')
    task.status = 'cancelled'
    task.error_message = payload.reason.strip() or '用户选择不投递'
    await db.commit()
    await db.refresh(task)
    return task

@router.post('/application-automation/tasks/{task_id}/submit', response_model=AutomationTaskRead)
async def submit(task_id: int, payload: AutomationSubmitRequest, db: AsyncSession=Depends(get_db), bridge: BrowserBridge=Depends(get_browser_bridge)) -> AutomatedApplicationTask:
    task = await require_task(db, task_id)
    if not payload.confirmed:
        raise HTTPException(status_code=400, detail='必须明确确认本次外部投递')
    if task.status != 'awaiting_confirmation':
        raise HTTPException(status_code=409, detail='任务尚未完成预览或已经提交')
    if payload.confirmation_token != task.confirmation_token:
        raise HTTPException(status_code=409, detail='预览已失效，请重新准备任务')
    await enforce_submission_policy(db, task)
    adapter = require_platform(task.platform_key)
    return await submit_task(db, task, adapter, bridge)
