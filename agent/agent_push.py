"""HTTP client for pushing agent data to the SaaS API."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30  # seconds


class _DTEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime objects."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def push_payload(
    saas_url: str,
    api_key: str,
    payload_dict: Dict[str, Any],
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """POST the agent payload to /api/agent/ingest.

    Returns the JSON response body on success, or raises on failure.
    """
    url = f"{saas_url.rstrip('/')}/api/agent/ingest"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = json.dumps(payload_dict, cls=_DTEncoder)
    resp = requests.post(url, data=body, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def fetch_config(
    saas_url: str,
    api_key: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """GET /api/agent/config — fetch OLT list from SaaS."""
    url = f"{saas_url.rstrip('/')}/api/agent/config"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def send_heartbeat(
    saas_url: str,
    api_key: str,
    timeout: int = 10,
) -> Dict[str, Any]:
    """POST a heartbeat to /api/agent/heartbeat."""
    url = f"{saas_url.rstrip('/')}/api/agent/heartbeat"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.post(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.json()
