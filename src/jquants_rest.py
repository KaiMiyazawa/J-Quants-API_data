from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple

import requests
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

log = logging.getLogger(__name__)


class RetryableHttpError(RuntimeError):
    pass


@dataclass
class JQuantsRestClient:
    api_key: str
    base_url: str
    timeout_sec: int
    max_retry: int
    retry_base_sleep_sec: int

    def _headers(self) -> Dict[str, str]:
        return {"x-api-key": self.api_key}

    def _url(self, endpoint: str) -> str:
        return f"{self.base_url.rstrip('/')}{endpoint}"

    def _retryable(self):
        return retry(
            stop=stop_after_attempt(self.max_retry),
            wait=wait_exponential_jitter(initial=self.retry_base_sleep_sec, max=120),
            reraise=True,
        )

    def _request_once(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = self._url(endpoint)
        res = requests.get(url, params=params, headers=self._headers(), timeout=self.timeout_sec)

        if res.status_code == 210:
            # Not available window (e.g. daily/am). Treat as empty.
            log.warning("Status 210 for %s params=%s", endpoint, params)
            return {"data": [], "pagination_key": None}

        if res.status_code == 429 or 500 <= res.status_code < 600:
            raise RetryableHttpError(f"HTTP {res.status_code}: {res.text}")

        if res.status_code != 200:
            if res.status_code == 400 and "subscription covers" in res.text:
                raise RuntimeError(
                    f"HTTP 400: {res.text} (adjust the date range to the covered window)"
                )
            raise RuntimeError(f"HTTP {res.status_code}: {res.text}")

        return res.json()

    def request_json(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        @_decorator(self._retryable())
        def _call():
            return self._request_once(endpoint, params)

        return _call()

    def iter_pages(
        self,
        endpoint: str,
        params: Dict[str, Any],
        rate_limiter: Optional[Any] = None,
    ) -> Iterable[Tuple[int, list[dict[str, Any]], Optional[str]]]:
        page = 0
        next_key: Optional[str] = params.get("pagination_key")
        current_params = dict(params)

        while True:
            if rate_limiter is not None:
                rate_limiter.acquire(1.0)
            data = self.request_json(endpoint, current_params)
            rows = data.get("data", [])
            next_key = data.get("pagination_key")
            page += 1
            yield page, rows, next_key

            if not next_key:
                break
            current_params["pagination_key"] = next_key


# Helper to allow decorator creation inside method without nesting lint issues

def _decorator(tenacity_decorator):
    def _wrap(fn):
        return tenacity_decorator(fn)

    return _wrap
