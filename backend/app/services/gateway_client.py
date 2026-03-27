import json
import threading
import time
from collections.abc import Mapping

import httpx

from ..config import Settings
from .log_broker import LogBroker


class GatewayClient:
    def __init__(self, settings: Settings, log_broker: LogBroker):
        self.settings = settings
        self.log_broker = log_broker
        self._lock = threading.Lock()
        self._last_attempt_ts: float = 0.0

    def _parse_json(self, raw: str, fallback: dict) -> dict:
        if not raw:
            return fallback
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, Mapping):
                return dict(parsed)
        except json.JSONDecodeError:
            pass
        return fallback

    def connect(self, reason: str = "manual", force: bool = False) -> tuple[bool, str]:
        if not self.settings.gateway_url:
            message = "Gateway URL is not configured. Skipping connect request."
            self.log_broker.publish("picoclaw", "system", message, source="system")
            return False, message

        with self._lock:
            now = time.monotonic()
            min_interval = max(0.0, self.settings.gateway_min_interval_seconds)
            if not force and now - self._last_attempt_ts < min_interval:
                wait_for = round(min_interval - (now - self._last_attempt_ts), 1)
                message = f"Gateway auto-connect is cooling down ({wait_for}s remaining)."
                self.log_broker.publish("picoclaw", "system", message, source="system")
                return False, message
            self._last_attempt_ts = now

        headers = self._parse_json(self.settings.gateway_headers_json, {})
        body = self._parse_json(self.settings.gateway_body_json, {})
        method = self.settings.gateway_method.upper().strip() or "POST"

        retries = max(1, self.settings.gateway_retries)
        for attempt in range(1, retries + 1):
            try:
                self.log_broker.publish(
                    "picoclaw",
                    "system",
                    f"Gateway connect attempt {attempt}/{retries} ({reason})",
                    source="system",
                )
                response = httpx.request(
                    method=method,
                    url=self.settings.gateway_url,
                    headers=headers,
                    json=body if body else None,
                    timeout=self.settings.gateway_timeout_seconds,
                )
                if 200 <= response.status_code < 300:
                    message = f"Gateway connected successfully ({response.status_code})."
                    self.log_broker.publish("picoclaw", "system", message, source="system")
                    return True, message
                message = f"Gateway returned {response.status_code}: {response.text[:200]}"
                self.log_broker.publish("picoclaw", "stderr", message, source="system")
            except Exception as exc:
                message = f"Gateway connect failed: {exc}"
                self.log_broker.publish("picoclaw", "stderr", message, source="system")

            if attempt < retries:
                time.sleep(max(0.0, self.settings.gateway_backoff_seconds))

        return False, "Gateway connect failed after retries."

