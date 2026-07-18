import httpx
import pytest

from app.services import email_delivery
from app.services.email_delivery import EmailDeliveryUnavailable, send_verification_email


def test_brevo_provider_sends_verification_code_over_https(monkeypatch):
    captured: dict[str, object] = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return httpx.Response(201, request=httpx.Request("POST", url))

    monkeypatch.setattr(email_delivery.settings, "email_delivery_provider", "brevo")
    monkeypatch.setattr(email_delivery.settings, "brevo_api_key", "test-api-key")
    monkeypatch.setattr(email_delivery.settings, "brevo_sender_email", "noreply@example.com")
    monkeypatch.setattr(email_delivery.settings, "brevo_sender_name", "CareerPilot AI")
    monkeypatch.setattr(email_delivery.httpx, "post", fake_post)

    send_verification_email("12345678@qq.com", "654321", "register")

    assert captured["url"] == "https://api.brevo.com/v3/smtp/email"
    assert captured["headers"] == {
        "api-key": "test-api-key",
        "accept": "application/json",
        "content-type": "application/json",
    }
    assert captured["json"] == {
        "sender": {"name": "CareerPilot AI", "email": "noreply@example.com"},
        "to": [{"email": "12345678@qq.com"}],
        "subject": "CareerPilot AI 注册验证码",
        "textContent": "你的验证码是：654321\n\n验证码 5 分钟内有效。若非本人操作，请忽略本邮件。",
    }
    assert captured["timeout"] == 15


def test_brevo_provider_requires_secret_and_verified_sender(monkeypatch):
    monkeypatch.setattr(email_delivery.settings, "email_delivery_provider", "brevo")
    monkeypatch.setattr(email_delivery.settings, "brevo_api_key", "")
    monkeypatch.setattr(email_delivery.settings, "brevo_sender_email", "")

    with pytest.raises(EmailDeliveryUnavailable, match="Brevo HTTPS 发信服务尚未配置"):
        send_verification_email("12345678@qq.com", "654321", "login")


def test_auto_provider_keeps_smtp_fallback(monkeypatch):
    sent: dict[str, object] = {}

    class FakeSmtp:
        def __init__(self, host, port, timeout):
            sent.update(host=host, port=port, timeout=timeout)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def login(self, username, password):
            sent.update(username=username, password=password)

        def send_message(self, message):
            sent["recipient"] = message["To"]

    monkeypatch.setattr(email_delivery.settings, "email_delivery_provider", "auto")
    monkeypatch.setattr(email_delivery.settings, "brevo_api_key", "")
    monkeypatch.setattr(email_delivery.settings, "brevo_sender_email", "")
    monkeypatch.setattr(email_delivery.settings, "smtp_username", "sender@qq.com")
    monkeypatch.setattr(email_delivery.settings, "smtp_authorization_code", "smtp-secret")
    monkeypatch.setattr(email_delivery.smtplib, "SMTP_SSL", FakeSmtp)

    send_verification_email("12345678@qq.com", "654321", "reset_password")

    assert sent["username"] == "sender@qq.com"
    assert sent["recipient"] == "12345678@qq.com"


def test_relay_provider_sends_only_code_payload_over_https(monkeypatch):
    captured: dict[str, object] = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return httpx.Response(204, request=httpx.Request("POST", url))

    monkeypatch.setattr(email_delivery.settings, "email_delivery_provider", "relay")
    monkeypatch.setattr(email_delivery.settings, "email_relay_url", "https://relay.example.com/api/internal/email-relay")
    monkeypatch.setattr(email_delivery.settings, "email_relay_token", "r" * 48)
    monkeypatch.setattr(email_delivery.httpx, "post", fake_post)

    send_verification_email("12345678@qq.com", "654321", "login")

    assert captured["url"] == "https://relay.example.com/api/internal/email-relay"
    assert captured["headers"] == {"authorization": f"Bearer {'r' * 48}"}
    assert captured["json"] == {
        "recipient": "12345678@qq.com",
        "code": "654321",
        "purpose": "login",
    }
    assert captured["timeout"] == 15


def test_relay_provider_requires_https_and_long_secret(monkeypatch):
    monkeypatch.setattr(email_delivery.settings, "email_delivery_provider", "relay")
    monkeypatch.setattr(email_delivery.settings, "email_relay_url", "http://relay.example.com/api/internal/email-relay")
    monkeypatch.setattr(email_delivery.settings, "email_relay_token", "short")

    with pytest.raises(EmailDeliveryUnavailable, match="邮件中继尚未安全配置"):
        send_verification_email("12345678@qq.com", "654321", "login")


def test_internal_relay_rejects_wrong_token(client, monkeypatch):
    from app.api.routes import internal_email_relay

    monkeypatch.setattr(internal_email_relay.settings, "email_relay_token", "r" * 48)

    response = client.post(
        "/api/internal/email-relay",
        headers={"authorization": "Bearer wrong"},
        json={"recipient": "12345678@qq.com", "code": "654321", "purpose": "register"},
    )

    assert response.status_code == 401


def test_internal_relay_sends_qq_verification_email(client, monkeypatch):
    from app.api.routes import internal_email_relay

    sent: dict[str, str] = {}
    monkeypatch.setattr(internal_email_relay.settings, "email_relay_token", "r" * 48)
    monkeypatch.setattr(
        internal_email_relay,
        "send_verification_email_smtp",
        lambda recipient, code, purpose: sent.update(
            recipient=recipient,
            code=code,
            purpose=purpose,
        ),
    )

    response = client.post(
        "/api/internal/email-relay",
        headers={"authorization": f"Bearer {'r' * 48}"},
        json={"recipient": "12345678@qq.com", "code": "654321", "purpose": "reset_password"},
    )

    assert response.status_code == 204
    assert sent == {
        "recipient": "12345678@qq.com",
        "code": "654321",
        "purpose": "reset_password",
    }
