import smtplib
from email.message import EmailMessage
from email.utils import formataddr

import httpx

from app.core.config import settings


class EmailDeliveryUnavailable(RuntimeError):
    pass


def _verification_content(code: str, purpose: str) -> tuple[str, str]:
    subject_by_purpose = {
        "register": "注册验证码",
        "login": "登录验证码",
        "reset_password": "重置密码验证码",
    }
    subject = f"CareerPilot AI {subject_by_purpose[purpose]}"
    content = f"你的验证码是：{code}\n\n验证码 5 分钟内有效。若非本人操作，请忽略本邮件。"
    return subject, content


def _send_with_brevo(recipient: str, subject: str, content: str) -> None:
    if not settings.brevo_api_key or not settings.brevo_sender_email:
        raise EmailDeliveryUnavailable("Brevo HTTPS 发信服务尚未配置")
    try:
        response = httpx.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": settings.brevo_api_key,
                "accept": "application/json",
                "content-type": "application/json",
            },
            json={
                "sender": {
                    "name": settings.brevo_sender_name,
                    "email": settings.brevo_sender_email,
                },
                "to": [{"email": recipient}],
                "subject": subject,
                "textContent": content,
            },
            timeout=15,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise EmailDeliveryUnavailable("Brevo HTTPS 发信服务暂时不可用") from exc


def _send_with_smtp(recipient: str, subject: str, content: str) -> None:
    if not settings.smtp_username or not settings.smtp_authorization_code:
        raise EmailDeliveryUnavailable("QQ 邮箱发信服务尚未配置")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((settings.smtp_sender_name, settings.smtp_username))
    message["To"] = recipient
    message.set_content(content)

    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.login(settings.smtp_username, settings.smtp_authorization_code)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_username, settings.smtp_authorization_code)
            smtp.send_message(message)


def _send_with_relay(recipient: str, code: str, purpose: str) -> None:
    relay_url = settings.email_relay_url.strip()
    relay_token = settings.email_relay_token.strip()
    if not relay_url.startswith("https://") or len(relay_token) < 32:
        raise EmailDeliveryUnavailable("HTTPS 邮件中继尚未安全配置")
    try:
        response = httpx.post(
            relay_url,
            headers={"authorization": f"Bearer {relay_token}"},
            json={"recipient": recipient, "code": code, "purpose": purpose},
            timeout=15,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise EmailDeliveryUnavailable("本机 QQ 邮件中继暂时不可用") from exc


def send_verification_email_smtp(recipient: str, code: str, purpose: str) -> None:
    subject, content = _verification_content(code, purpose)
    _send_with_smtp(recipient, subject, content)


def send_verification_email(recipient: str, code: str, purpose: str) -> None:
    subject, content = _verification_content(code, purpose)
    provider = settings.email_delivery_provider.strip().lower()
    if provider == "relay":
        _send_with_relay(recipient, code, purpose)
        return
    if provider == "brevo" or (
        provider == "auto" and settings.brevo_api_key and settings.brevo_sender_email
    ):
        _send_with_brevo(recipient, subject, content)
        return
    if provider in {"auto", "smtp"}:
        _send_with_smtp(recipient, subject, content)
        return
    raise EmailDeliveryUnavailable("未知的邮件发送服务配置")
