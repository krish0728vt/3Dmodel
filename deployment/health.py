"""HTTP health probing used while waiting for child servers to come up."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any


def probe_json(url: str, *, timeout: float = 3.0) -> dict[str, Any] | None:
    """GET `url` and decode JSON, or None if it is not reachable/parseable."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - fixed localhost URL
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None
    return payload if isinstance(payload, dict) else None


def probe_ok(url: str, *, timeout: float = 3.0) -> bool:
    """True when `url` answers with any 2xx/3xx status.

    Used for the frontend, which serves HTML rather than JSON.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - fixed localhost URL
            return 200 <= response.status < 400
    except urllib.error.HTTPError as exc:
        return 200 <= exc.code < 400
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def wait_for_backend(
    base_url: str,
    *,
    timeout: float = 30.0,
    interval: float = 0.4,
    is_alive: Any = None,
) -> dict[str, Any] | None:
    """Poll `/api/health` until it answers, the process dies, or time runs out.

    `is_alive` is an optional zero-argument callable; when it returns False the
    wait aborts immediately so a crashed server fails fast instead of burning
    the full timeout.
    """
    deadline = time.monotonic() + timeout
    url = f"{base_url.rstrip('/')}/api/health"
    while time.monotonic() < deadline:
        if is_alive is not None and not is_alive():
            return None
        payload = probe_json(url)
        if payload is not None and payload.get("status") == "online":
            return payload
        time.sleep(interval)
    return None


def wait_for_frontend(
    base_url: str,
    *,
    timeout: float = 30.0,
    interval: float = 0.4,
    is_alive: Any = None,
) -> bool:
    """Poll the dev server root until it serves something."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_alive is not None and not is_alive():
            return False
        if probe_ok(base_url):
            return True
        time.sleep(interval)
    return False
