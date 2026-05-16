"""
Shared HTTP session with retries and sensible defaults.

Every service module should import `session` from here instead of
creating its own ``requests.Session``.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import Config


def _build_session() -> requests.Session:
    """Create a requests session with automatic retries."""
    s = requests.Session()

    retry_strategy = Retry(
        total=Config.HTTP_RETRIES,
        backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    s.mount("https://", adapter)
    s.mount("http://", adapter)

    s.headers.update({
        "User-Agent": "SATO-Agro/1.0 (hackathon MVP)",
        "Accept": "application/json, text/html, */*",
    })

    return s


session = _build_session()


def get_json(url: str, params: dict | None = None) -> dict:
    """GET a URL and return decoded JSON, raising on HTTP errors."""
    resp = session.get(url, params=params, timeout=Config.HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def get_html(url: str) -> str:
    """GET a URL and return the response text (HTML)."""
    resp = session.get(url, timeout=Config.HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def head(url: str) -> dict:
    """HEAD a URL and return response headers as a dict."""
    resp = session.head(url, timeout=Config.HTTP_TIMEOUT, allow_redirects=True)
    resp.raise_for_status()
    return dict(resp.headers)
