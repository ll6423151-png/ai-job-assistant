import json
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.application_automation import AutomatedApplicationTask
from app.models.application_record import ApplicationRecord
from app.models.blacklist_company import BlacklistCompany
from app.platforms.base import PlatformAdapter
from app.services.browser_bridge import BrowserBridge, BrowserBridgeError

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def validate_platform_url(url: str, adapter: PlatformAdapter) -> bool:
    host = (urlparse(url).hostname or '').lower()
    return bool(host) and any((host == allowed or host.endswith(f'.{allowed}') for allowed in adapter.allowed_hosts))

async def find_blacklist_match(db: AsyncSession, company_name: str) -> BlacklistCompany | None:
    candidate = company_name.strip().casefold()
    if not candidate:
        return None
    rules = (await db.scalars(select(BlacklistCompany).where(BlacklistCompany.is_active.is_(True)))).all()
    for rule in rules:
        blocked = rule.company_name.strip().casefold()
        if rule.match_type == 'contains' and blocked in candidate:
            return rule
        if rule.match_type == 'exact' and blocked == candidate:
            return rule
    return None

async def ensure_company_blacklisted(db: AsyncSession, company_name: str, reason: str) -> BlacklistCompany | None:
    normalized = company_name.strip()
    if not normalized:
        return None
    existing = next((rule for rule in (await db.scalars(select(BlacklistCompany))).all() if rule.company_name.strip().casefold() == normalized.casefold()), None)
    if existing is not None:
        existing.is_active = True
        if not existing.reason or '自动' in existing.reason:
            existing.reason = reason
        await db.flush()
        return existing
    rule = BlacklistCompany(company_name=normalized, match_type='exact', reason=reason, is_active=True)
    db.add(rule)
    await db.flush()
    return rule

def _as_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}

def inspect_page(bridge: BrowserBridge, target_id: str, adapter: PlatformAdapter) -> dict[str, object]:
    labels = json.dumps(adapter.apply_labels, ensure_ascii=True)
    script = f"""(() => {{\n      const labels = {labels};\n      const visible = (element) => {{\n        const style = getComputedStyle(element);\n        const rect = element.getBoundingClientRect();\n        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;\n      }};\n      const controls = [...document.querySelectorAll('button, a, [role="button"], .btn-startchat, .resume_apply, .com_res')]\n        .filter(visible)\n        .map((element) => ({{ text: (element.innerText || element.textContent || '').trim().replace(/\\s+/g, ' ') }}))\n        .filter((item) => item.text && labels.some((label) => item.text.includes(label)));\n      return {{\n        url: location.href,\n        title: document.title,\n        body_text: (document.body?.innerText || '').slice(0, 12000),\n        apply_controls: controls.slice(0, 10),\n      }};\n    }})()"""
    return _as_dict(bridge.evaluate(target_id, script))

def detect_login_status(page: dict[str, object], adapter: PlatformAdapter) -> tuple[str, list[str]]:
    body = str(page.get('body_text', ''))
    logged_in = [marker for marker in adapter.logged_in_markers if marker in body]
    logged_out = [marker for marker in adapter.logged_out_markers if marker in body]
    if logged_in:
        return ('logged_in', logged_in[:3])
    if logged_out:
        return ('logged_out', logged_out[:3])
    return ('unknown', [])

async def prepare_task(db: AsyncSession, task: AutomatedApplicationTask, adapter: PlatformAdapter, bridge: BrowserBridge) -> AutomatedApplicationTask:
    if task.status not in {'draft', 'awaiting_login', 'failed'}:
        return task
    if not validate_platform_url(task.job_url_snapshot, adapter):
        task.status = 'failed'
        task.error_message = f'岗位链接不属于{adapter.name}'
        await db.commit()
        return task
    try:
        target_id = bridge.open_url(task.job_url_snapshot)
        time.sleep(0.8)
        page = inspect_page(bridge, target_id, adapter)
    except BrowserBridgeError as exc:
        task.status = 'awaiting_login'
        task.error_message = str(exc)
        await db.commit()
        return task
    login_status, evidence = detect_login_status(page, adapter)
    controls = page.get('apply_controls', [])
    warnings: list[str] = []
    if login_status == 'unknown':
        warnings.append('无法完全确认登录状态，请在提交前核对平台页面。')
    if adapter.key == 'zhaopin':
        warnings.append('智联可能直接使用平台默认简历；仅在平台弹出简历选择框时按名称选择。')
        if task.greeting_snapshot:
            warnings.append('投递成功后将尝试发送沟通内容；若智联 PC 网页仅显示 APP 提示，任务会标记为需手动发送。')
    task.browser_target_id = target_id
    task.preview = {'page_title': page.get('title', ''), 'page_url': page.get('url', task.job_url_snapshot), 'login_status': login_status, 'login_evidence': evidence, 'apply_controls': controls, 'job_title': task.job_title_snapshot, 'company': task.company_snapshot, 'resume_title': task.resume_title_snapshot, 'greeting': task.greeting_snapshot, 'submission_policy': {'daily_limit': settings.application_automation_daily_limit, 'cooldown_seconds': settings.application_automation_cooldown_seconds}, 'warnings': warnings}
    task.prepared_at = now_utc()
    task.confirmation_token = uuid4().hex
    task.error_message = ''
    if login_status == 'logged_out':
        task.status = 'awaiting_login'
        task.error_message = f'请先在浏览器中登录{adapter.name}'
    elif not controls:
        task.status = 'failed'
        task.error_message = '当前页面未找到可用的投递或沟通按钮，请核对岗位链接'
    else:
        task.status = 'awaiting_confirmation'
    await db.commit()
    await db.refresh(task)
    return task

def _click_matching_control(bridge: BrowserBridge, target_id: str, labels: tuple[str, ...], modal_only: bool=False) -> dict[str, object]:
    labels_json = json.dumps(labels, ensure_ascii=True)
    root = "document.querySelector('[role=dialog], .modal, .dialog, .el-dialog')" if modal_only else 'document'
    script = f"""(() => {{\n      const labels = {labels_json};\n      const root = {root};\n      if (!root) return {{ clicked: false, reason: 'container_not_found' }};\n      const visible = (element) => {{\n        const style = getComputedStyle(element);\n        const rect = element.getBoundingClientRect();\n        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;\n      }};\n      const element = [...root.querySelectorAll('button, a, [role="button"], .btn-startchat, .resume_apply, .com_res')].find((candidate) => {{\n        const text = (candidate.innerText || candidate.textContent || '').trim().replace(/\\s+/g, ' ');\n        return visible(candidate) && labels.some((label) => text.includes(label));\n      }});\n      if (!element) return {{ clicked: false, reason: 'control_not_found' }};\n      const text = (element.innerText || element.textContent || '').trim().replace(/\\s+/g, ' ');\n      element.scrollIntoView({{ block: 'center' }});\n      element.click();\n      return {{ clicked: true, text }};\n    }})()"""
    return _as_dict(bridge.evaluate(target_id, script))

def _inspect_resume_selection_dialog(bridge: BrowserBridge, target_id: str) -> dict[str, object]:
    script = "(() => {\n      const panel = document.querySelector('.a-job-apply-resume-selection-panel');\n      if (!panel) return { visible: false, selected_label: '', resume_options: [] };\n      const style = getComputedStyle(panel);\n      const rect = panel.getBoundingClientRect();\n      const visible = style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;\n      const options = [...document.querySelectorAll('.a-selector-option')]\n        .map((item) => (item.innerText || item.textContent || '').trim().replace(/\\s+/g, ' '))\n        .filter(Boolean);\n      return {\n        visible,\n        selected_label: (panel.querySelector('.a-job-apply-resume-selection-panel__resumes-select .a-selector__content label')?.innerText || '').trim(),\n        resume_options: options,\n      };\n    })() // a-job-apply-resume-selection-panel"
    return _as_dict(bridge.evaluate(target_id, script))

def _select_dialog_resume(bridge: BrowserBridge, target_id: str, resume_title: str) -> dict[str, object]:
    open_script = "(() => {\n      const control = document.querySelector('.a-job-apply-resume-selection-panel__resumes-select .a-selector__content');\n      if (!control) return { opened: false };\n      control.click();\n      return { opened: true };\n    })() // a-selector__content"
    bridge.evaluate(target_id, open_script)
    time.sleep(0.25)
    title_json = json.dumps(resume_title, ensure_ascii=True)
    select_script = f"(() => {{\n      const desired = {title_json}.trim().toLocaleLowerCase();\n      const options = [...document.querySelectorAll('.a-selector-option')].filter((item) => {{\n        const style = getComputedStyle(item);\n        const rect = item.getBoundingClientRect();\n        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;\n      }});\n      const text = (item) => (item.innerText || item.textContent || '').trim().replace(/\\s+/g, ' ');\n      const matched = options.find((item) => text(item).toLocaleLowerCase() === desired)\n        || options.find((item) => text(item).toLocaleLowerCase().includes(desired) || desired.includes(text(item).toLocaleLowerCase()))\n        || (options.length === 1 ? options[0] : null);\n      if (!matched) return {{ selected: false, options: options.map(text) }};\n      const selectedText = text(matched);\n      matched.click();\n      return {{ selected: true, selected_text: selectedText, options: options.map(text) }};\n    }})() // a-selector-option"
    return _as_dict(bridge.evaluate(target_id, select_script))

def _click_resume_dialog_delivery(bridge: BrowserBridge, target_id: str) -> dict[str, object]:
    script = "(() => {\n      const button = document.querySelector('.a-job-apply-resume-selection-panel__deliver');\n      if (!button) return { clicked: false, reason: 'deliver_control_not_found' };\n      const disabled = button.matches('.a--disabled,[disabled]');\n      if (disabled) return { clicked: false, reason: 'deliver_control_disabled' };\n      const text = (button.innerText || button.textContent || '').trim().replace(/\\s+/g, ' ');\n      button.click();\n      return { clicked: true, text };\n    })() // a-job-apply-resume-selection-panel__deliver"
    return _as_dict(bridge.evaluate(target_id, script))

def _open_post_apply_communication(bridge: BrowserBridge, target_id: str) -> dict[str, object]:
    script = '(() => {\n      const visible = (element) => {\n        const style = getComputedStyle(element);\n        const rect = element.getBoundingClientRect();\n        return style.display !== \'none\' && style.visibility !== \'hidden\' && rect.width > 0 && rect.height > 0;\n      };\n      const control = [...document.querySelectorAll(\'button, a, [role="button"]\')]\n        .find((candidate) => visible(candidate) && /立即沟通|继续沟通|联系HR/.test((candidate.innerText || candidate.textContent || \'\').trim()));\n      if (!control) return { clicked: false, reason: \'communication_control_not_found\' };\n      const text = (control.innerText || control.textContent || \'\').trim().replace(/\\s+/g, \' \');\n      control.scrollIntoView({ block: \'center\' });\n      control.click();\n      return { clicked: true, text };\n    })() // post-apply-communication-open'
    return _as_dict(bridge.evaluate(target_id, script))

def _fill_and_send_post_apply_greeting(bridge: BrowserBridge, target_id: str, message: str) -> dict[str, object]:
    message_json = json.dumps(message, ensure_ascii=True)
    script = f"""(() => {{\n      const message = {message_json};\n      const visible = (element) => {{\n        const style = getComputedStyle(element);\n        const rect = element.getBoundingClientRect();\n        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;\n      }};\n      const inputSelectors = [\n        '[role="dialog"] textarea',\n        '[role="dialog"] [contenteditable="true"]',\n        '[class*="chat"] textarea',\n        '[class*="chat"] [contenteditable="true"]',\n        '[class*="message"] textarea',\n        '[class*="message"] [contenteditable="true"]'\n      ];\n      const input = inputSelectors.flatMap((selector) => [...document.querySelectorAll(selector)])\n        .find((candidate) => visible(candidate));\n      if (!input) {{\n        const body = document.body?.innerText || '';\n        return {{\n          status: 'manual_required',\n          sent: false,\n          reason: /下载智联APP|下载APP/.test(body)\n            ? '智联 PC 网页仅提供 APP 下载提示，没有消息输入框'\n            : '当前页面没有可用的 HR 消息输入框'\n        }};\n      }}\n      if (input instanceof HTMLInputElement || input instanceof HTMLTextAreaElement) {{\n        const prototype = input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;\n        const setter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;\n        if (setter) setter.call(input, message); else input.value = message;\n      }} else {{\n        input.textContent = message;\n      }}\n      input.dispatchEvent(new InputEvent('input', {{ bubbles: true, inputType: 'insertText', data: message }}));\n      input.dispatchEvent(new Event('change', {{ bubbles: true }}));\n      const container = input.closest('[role="dialog"], [class*="chat"], [class*="message"]') || document;\n      const send = [...container.querySelectorAll('button, [role="button"]')].find((candidate) => {{\n        const text = (candidate.innerText || candidate.textContent || '').trim().replace(/\\s+/g, ' ');\n        return visible(candidate) && !candidate.matches('[disabled], .disabled, .a--disabled') && /^(发送|发送消息)$/.test(text);\n      }});\n      if (!send) return {{ status: 'manual_required', sent: false, reason: '已找到消息输入框，但没有可用的发送按钮' }};\n      send.click();\n      return {{ status: 'send_clicked', sent: false, message_length: message.length }};\n    }})() // post-apply-communication-send"""
    result = _as_dict(bridge.evaluate(target_id, script))
    if result.get('status') != 'send_clicked':
        return result
    time.sleep(0.6)
    verify_script = f"""(() => {{\n      const message = {message_json};\n      const inputs = [...document.querySelectorAll(\n        '[role="dialog"] textarea, [role="dialog"] [contenteditable="true"], [class*="chat"] textarea, [class*="chat"] [contenteditable="true"], [class*="message"] textarea, [class*="message"] [contenteditable="true"]'\n      )];\n      const value = (element) => 'value' in element ? element.value : (element.textContent || '');\n      const cleared = inputs.length > 0 && inputs.every((element) => !value(element).trim());\n      const echoed = [...document.querySelectorAll('[class*="message"], [class*="chat"]')]\n        .some((element) => (element.innerText || '').includes(message));\n      return cleared || echoed\n        ? {{ status: 'sent', sent: true, evidence: cleared ? 'message_input_cleared' : 'outgoing_message_visible' }}\n        : {{ status: 'verification_required', sent: false, reason: '已点击发送，但页面未显示明确发送成功证据' }};\n    }})() // post-apply-communication-verify"""
    return _as_dict(bridge.evaluate(target_id, verify_script))

def send_post_apply_greeting(bridge: BrowserBridge, target_id: str, message: str) -> dict[str, object]:
    content = message.strip()
    if not content:
        return {'requested': False, 'status': 'not_requested', 'sent': False}
    opened = _open_post_apply_communication(bridge, target_id)
    if not opened.get('clicked'):
        return {'requested': True, 'status': 'manual_required', 'sent': False, 'reason': '投递成功后未找到 HR 沟通入口', 'open_result': opened}
    time.sleep(0.4)
    result = _fill_and_send_post_apply_greeting(bridge, target_id, content)
    result['requested'] = True
    result['open_result'] = opened
    return result

async def _create_application_record(db: AsyncSession, task: AutomatedApplicationTask, verified: bool, communication: dict[str, object] | None=None) -> ApplicationRecord:
    timestamp = now_utc()
    status = 'submitted' if verified else 'prepared'
    note = '平台页面已验证投递成功' if verified else '已执行平台投递操作，等待人工核验结果'
    communication_status = str((communication or {}).get('status', ''))
    if communication_status == 'sent':
        note += '；投递后沟通内容已发送'
    elif communication_status in {'manual_required', 'verification_required'}:
        note += '；投递后沟通内容待人工处理'
    record = ApplicationRecord(job_id=task.job_id, resume_id=task.resume_id, greeting_id=task.greeting_id, job_title=task.job_title_snapshot, company_name=task.company_snapshot, resume_title=task.resume_title_snapshot, channel=task.platform_key, status=status, confirmed_by_user=True, applied_at=timestamp if verified else None, notes=note, status_history=[{'status': status, 'timestamp': timestamp.isoformat(), 'note': note}])
    db.add(record)
    await db.flush()
    task.application_record_id = record.id
    return record

async def submit_task(db: AsyncSession, task: AutomatedApplicationTask, adapter: PlatformAdapter, bridge: BrowserBridge) -> AutomatedApplicationTask:
    if task.status != 'awaiting_confirmation':
        return task
    task.status = 'submitting'
    task.confirmed_by_user = True
    task.submitted_at = now_utc()
    await db.commit()
    try:
        first_click = _click_matching_control(bridge, task.browser_target_id, adapter.apply_labels)
        if not first_click.get('clicked'):
            raise BrowserBridgeError('未找到可点击的投递入口，页面可能已变化')
        time.sleep(1.2)
        second_click: dict[str, object] = {'clicked': False}
        resume_dialog = _inspect_resume_selection_dialog(bridge, task.browser_target_id)
        resume_selection: dict[str, object] = {'dialog_visible': bool(resume_dialog.get('visible')), 'selected': False, 'mode': 'platform_default'}
        if resume_dialog.get('visible'):
            resume_selection = _select_dialog_resume(bridge, task.browser_target_id, task.resume_title_snapshot)
            resume_selection['dialog_visible'] = True
            resume_selection['mode'] = 'platform_dialog'
            if not resume_selection.get('selected'):
                raise BrowserBridgeError('智联弹窗未找到与本地任务同名的简历，请在平台手动选择后重试')
            second_click = _click_resume_dialog_delivery(bridge, task.browser_target_id)
            if not second_click.get('clicked'):
                raise BrowserBridgeError('智联简历弹窗未找到可用的立即申请按钮')
            time.sleep(1.2)
        elif adapter.requires_second_confirmation:
            second_click = _click_matching_control(bridge, task.browser_target_id, adapter.confirmation_labels, modal_only=True)
            if second_click.get('clicked'):
                time.sleep(1.2)
        page = inspect_page(bridge, task.browser_target_id, adapter)
        body = str(page.get('body_text', ''))
        success_evidence = [marker for marker in adapter.success_markers if marker in body]
        verified = bool(success_evidence)
        if verified:
            try:
                communication = await send_post_apply_greeting(bridge, task.browser_target_id, task.greeting_snapshot)
            except BrowserBridgeError as exc:
                communication = {'requested': bool(task.greeting_snapshot.strip()), 'status': 'manual_required', 'sent': False, 'reason': f'投递已成功，但沟通入口读取失败：{exc}'}
        else:
            communication = {'requested': bool(task.greeting_snapshot.strip()), 'status': 'awaiting_application_verification' if task.greeting_snapshot.strip() else 'not_requested', 'sent': False}
        task.status = 'submitted' if verified else 'verification_required'
        task.external_result = {'first_click': first_click, 'second_click': second_click, 'resume_selection': resume_selection, 'greeting_supported': communication.get('status') in {'sent', 'verification_required'}, 'greeting_filled': bool(communication.get('sent')), 'communication': communication, 'verified': verified, 'success_evidence': success_evidence, 'page_url': page.get('url', ''), 'page_title': page.get('title', '')}
        if not verified:
            task.error_message = '平台未显示明确成功标识，请人工核验'
        elif communication.get('status') in {'manual_required', 'verification_required'}:
            task.error_message = str(communication.get('reason', '投递成功，但沟通内容需要人工核验'))
        else:
            task.error_message = ''
        await _create_application_record(db, task, verified, communication)
    except BrowserBridgeError as exc:
        task.status = 'failed'
        task.error_message = str(exc)
    await db.commit()
    await db.refresh(task)
    return task
