import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import settings


class EmailDeliveryUnavailable(RuntimeError):
    pass


def send_verification_email(recipient: str, code: str, purpose: str) -> None:
    if not settings.smtp_username or not settings.smtp_authorization_code:
        raise EmailDeliveryUnavailable("QQ 邮箱发信服务尚未配置")

    subject_by_purpose = {
        "register": "注册验证码",
        "login": "登录验证码",
        "reset_password": "重置密码验证码",
    }
    message = EmailMessage()
    message["Subject"] = f"CareerPilot AI {subject_by_purpose[purpose]}"
    message["From"] = formataddr((settings.smtp_sender_name, settings.smtp_username))
    message["To"] = recipient
    message.set_content(
        f"你的验证码是：{code}\n\n验证码 5 分钟内有效。若非本人操作，请忽略本邮件。"
    )

    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.login(settings.smtp_username, settings.smtp_authorization_code)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_username, settings.smtp_authorization_code)
            smtp.send_message(message)
