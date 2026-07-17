from starlette.requests import Request

from app.services import auth as auth_service


def test_api_responses_include_security_headers(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["permissions-policy"] == "camera=(), geolocation=(), microphone=(self)"


def test_production_api_responses_include_strict_transport_headers(client, monkeypatch):
    monkeypatch.setattr(auth_service.settings, "environment", "production")

    response = client.get("/api/health")

    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"


def test_production_client_ip_uses_originating_forwarded_address(monkeypatch):
    monkeypatch.setattr(auth_service.settings, "environment", "production")
    request = Request({
        "type": "http",
        "headers": [(b"x-forwarded-for", b"203.0.113.42, 10.0.0.10")],
        "client": ("10.0.0.10", 12345),
    })

    assert auth_service.request_ip_address(request) == "203.0.113.42"
