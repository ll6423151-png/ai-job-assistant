import argparse
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify QQ SMTP login and optionally send a test email.")
    parser.add_argument("--recipient", help="QQ email that receives the verification message")
    args = parser.parse_args()

    if not settings.smtp_username or not settings.smtp_authorization_code:
        raise SystemExit("SMTP_USERNAME and SMTP_AUTHORIZATION_CODE are required")

    message = None
    if args.recipient:
        message = EmailMessage()
        message["Subject"] = "CareerPilot AI SMTP 配置验证"
        message["From"] = formataddr((settings.smtp_sender_name, settings.smtp_username))
        message["To"] = args.recipient
        message.set_content("CareerPilot AI 已成功连接 QQ SMTP 并发送此测试邮件。")

    if settings.smtp_use_ssl:
        smtp_client = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15)
    else:
        smtp_client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)

    with smtp_client as smtp:
        if not settings.smtp_use_ssl:
            smtp.starttls()
        smtp.login(settings.smtp_username, settings.smtp_authorization_code)
        if message is not None:
            smtp.send_message(message)

    action = "登录并发送测试邮件" if message is not None else "登录"
    print(f"QQ SMTP {action}成功")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
