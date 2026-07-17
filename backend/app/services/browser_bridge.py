from urllib.parse import urlparse

import httpx

from app.core.config import settings


class BrowserBridgeError(RuntimeError):
    pass


def unwrap_proxy_payload(payload: object) -> object:
    if isinstance(payload, dict):
        if "result" in payload:
            return payload["result"]
        if "value" in payload:
            return payload["value"]
    return payload


class BrowserBridge:
    def __init__(self) -> None:
        self.base_url = settings.browser_proxy_url.rstrip("/")
        self.timeout = settings.browser_proxy_timeout_seconds

    def _client(self, timeout: int | None = None) -> httpx.Client:
        return httpx.Client(timeout=timeout or self.timeout, trust_env=False)

    def list_targets(self, timeout: int | None = None) -> list[dict[str, object]]:
        try:
            with self._client(timeout) as client:
                response = client.get(f"{self.base_url}/targets")
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            raise BrowserBridgeError(
                "浏览器桥接不可用，请先开启 Edge 远程调试并运行 web-access 连接"
            ) from exc
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            targets = payload.get("targets", [])
            return targets if isinstance(targets, list) else []
        return []

    def is_available(self) -> bool:
        try:
            self.list_targets(timeout=2)
            return True
        except BrowserBridgeError:
            return False

    def open_url(self, url: str) -> str:
        try:
            with self._client() as client:
                response = client.post(
                    f"{self.base_url}/new",
                    content=url.encode("utf-8"),
                    headers={"Content-Type": "text/plain; charset=utf-8"},
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            raise BrowserBridgeError("无法在浏览器中打开平台页面") from exc
        target_id = payload.get("targetId") or payload.get("id") or payload.get("target_id")
        if not target_id:
            raise BrowserBridgeError("浏览器桥接未返回页面标识")
        return str(target_id)

    def evaluate(self, target_id: str, script: str) -> object:
        try:
            with self._client() as client:
                response = client.post(
                    f"{self.base_url}/eval",
                    params={"target": target_id},
                    content=script.encode("utf-8"),
                    headers={"Content-Type": "text/plain; charset=utf-8"},
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            raise BrowserBridgeError("无法读取或操作招聘平台页面") from exc
        return unwrap_proxy_payload(payload)

    def close_target(self, target_id: str) -> None:
        try:
            with self._client() as client:
                response = client.get(
                    f"{self.base_url}/close",
                    params={"target": target_id},
                )
                response.raise_for_status()
        except Exception as exc:
            raise BrowserBridgeError("无法关闭招聘平台页面") from exc

    def find_target_for_hosts(self, hosts: tuple[str, ...]) -> str | None:
        for target in reversed(self.list_targets()):
            url = str(target.get("url", ""))
            host = (urlparse(url).hostname or "").lower()
            if any(host == allowed or host.endswith(f".{allowed}") for allowed in hosts):
                target_id = target.get("targetId") or target.get("id") or target.get("target_id")
                if target_id:
                    return str(target_id)
        return None


def get_browser_bridge() -> BrowserBridge:
    return BrowserBridge()
