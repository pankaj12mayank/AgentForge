from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import socket
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx

from prompt_generation.db import get_settings

_MAX_RETRIES = 3

_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}

# Networks reachable only on the local machine / LAN. Sending user API keys to
# these via a misconfigured Base URL is a data-leak risk, so default-block them.
_PRIVATE_NETWORKS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


def _check_base_url(base_url: str) -> tuple[bool, str]:
    """SSRF guard: refuse to send provider credentials to private/LAN hosts.

    Loopback (localhost / 127.x / ::1) is always allowed for local LLM servers.
    Set AGENTFORGE_ALLOW_LOCAL_LLM=1 to explicitly allow LAN-intended servers.
    """
    parsed = urlparse(base_url.strip() if "://" in base_url else "http://" + base_url.strip())
    scheme = (parsed.scheme or "http").lower()
    if scheme not in ("http", "https"):
        return False, "Base URL must use http:// or https://."
    host = parsed.hostname
    if not host:
        return True, ""
    if os.getenv("AGENTFORGE_ALLOW_LOCAL_LLM", "").strip() in ("1", "true", "yes"):
        return True, ""
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        return True, ""
    unique_ips = sorted({info[4][0] for info in infos})
    for ip_str in unique_ips:
        try:
            ip = ipaddress.ip_address(ip_str.split("%")[0])
        except ValueError:
            continue
        if ip.is_loopback:
            continue
        for net in _PRIVATE_NETWORKS:
            if ip in net:
                return (
                    False,
                    "Refusing to send provider credentials to a private/LAN address. "
                    "Set AGENTFORGE_ALLOW_LOCAL_LLM=1 to allow local LLM servers.",
                )
    return True, ""


async def _post_with_retry(client: httpx.AsyncClient, url: str, payload: Dict[str, Any], headers: Dict[str, str]) -> httpx.Response:
    """POST with exponential backoff on rate-limit / transient server errors."""
    for attempt in range(_MAX_RETRIES):
        res = await client.post(url, json=payload, headers=headers)
        if res.status_code not in _RETRYABLE_STATUS or attempt == _MAX_RETRIES - 1:
            return res
        await asyncio.sleep(0.5 * (2 ** attempt))
    return res  # pragma: no cover - unreachable, keeps type checkers happy


async def fetch_provider_models(base_url: str, api_key: str) -> Dict[str, Any]:
    """Fetch available models from the specified provider Base URL."""
    b_url = base_url.strip().rstrip("/")
    if not b_url:
        return {"ok": False, "message": "Base URL cannot be empty.", "models": []}

    ok, msg = _check_base_url(b_url)
    if not ok:
        return {"ok": False, "message": msg, "models": []}

    # Format models URL
    if b_url.endswith("/chat/completions"):
        models_url = b_url.replace("/chat/completions", "/models")
    elif b_url.endswith("/models"):
        models_url = b_url
    else:
        models_url = f"{b_url}/models"

    headers = {"Content-Type": "application/json"}
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(models_url, headers=headers)
            
            # If 404, try alternate path without trailing /v1 or with /v1
            if res.status_code == 404:
                alt_url = f"{b_url}/v1/models" if not b_url.endswith("/v1") else b_url.replace("/v1", "/models")
                res = await client.get(alt_url, headers=headers)

            if res.status_code != 200:
                try:
                    err_json = res.json()
                    err_msg = err_json.get("error", {}).get("message") or res.text[:200]
                except Exception:
                    err_msg = res.text[:200]
                return {
                    "ok": False,
                    "message": f"Failed to fetch models (HTTP {res.status_code}): {err_msg}",
                    "models": [],
                }

            data = res.json()
            model_ids: List[str] = []

            # Handle standard OpenAI format {"data": [{"id": "model_name"}, ...]}
            if isinstance(data, dict):
                items = data.get("data") or data.get("models") or []
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            m_id = item.get("id") or item.get("name") or item.get("model")
                            if m_id:
                                model_ids.append(str(m_id))
                        elif isinstance(item, str):
                            model_ids.append(item)

            if not model_ids:
                return {
                    "ok": False,
                    "message": "Connected successfully, but no model list was returned.",
                    "models": [],
                }

            # Deduplicate & sort
            unique_models = sorted(list(dict.fromkeys(model_ids)))
            return {
                "ok": True,
                "message": f"Fetched {len(unique_models)} models successfully!",
                "models": unique_models,
            }

    except httpx.TimeoutException:
        return {"ok": False, "message": "Connection timed out fetching models.", "models": []}
    except Exception as e:
        return {"ok": False, "message": f"Error fetching models: {str(e)}", "models": []}


async def test_provider_connection(
    base_url: str,
    model_name: str,
    api_key: str,
    provider_name: str = "Custom",
) -> Dict[str, Any]:
    """Test connection to the specified LLM provider by sending a lightweight completion request."""
    b_url = base_url.strip().rstrip("/")
    if not b_url:
        return {"ok": False, "message": "Base URL cannot be empty."}

    ok, msg = _check_base_url(b_url)
    if not ok:
        return {"ok": False, "message": msg}

    url = f"{b_url}/chat/completions" if not b_url.endswith("/chat/completions") else b_url

    headers = {"Content-Type": "application/json"}
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    payload = {
        "model": model_name.strip() or "default",
        "messages": [
            {"role": "user", "content": "Hi"}
        ],
        "max_tokens": 5,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            if res.status_code == 200:
                return {
                    "ok": True,
                    "message": f"Successfully connected to {provider_name} ({model_name})!",
                    "status_code": 200,
                }
            elif res.status_code == 401:
                return {
                    "ok": False,
                    "message": "Authentication failed. Please check your API Key.",
                    "status_code": 401,
                }
            elif res.status_code == 404:
                models_res = await fetch_provider_models(base_url, api_key)
                if models_res["ok"]:
                    return {
                        "ok": True,
                        "message": f"Connected to {provider_name} server successfully!",
                        "status_code": 200,
                    }
                return {
                    "ok": False,
                    "message": f"Endpoint not found (HTTP 404). Check Base URL ({b_url}).",
                    "status_code": 404,
                }
            else:
                try:
                    err_json = res.json()
                    err_msg = err_json.get("error", {}).get("message") or res.text[:200]
                except Exception:
                    err_msg = res.text[:200]
                return {
                    "ok": False,
                    "message": f"HTTP {res.status_code}: {err_msg}",
                    "status_code": res.status_code,
                }
    except httpx.TimeoutException:
        return {"ok": False, "message": "Connection timed out. Check network or Base URL."}
    except Exception as e:
        return {"ok": False, "message": f"Connection error: {str(e)}"}


async def generate_chat_completion(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.15,
) -> str:
    """Generate completion using the active provider settings in DB."""
    settings = get_settings(masked=False)

    base_url = settings.get("base_url", "").rstrip("/")
    model_name = settings.get("model_name", "")
    api_key = settings.get("api_key", "")

    if not base_url:
        raise RuntimeError("No LLM Provider Base URL configured. Please configure your settings.")
    if not model_name:
        raise RuntimeError("No LLM Model selected. Please fetch and select a model in Settings.")

    ok, msg = _check_base_url(base_url)
    if not ok:
        raise RuntimeError(msg)

    url = f"{base_url}/chat/completions" if not base_url.endswith("/chat/completions") else base_url

    headers = {"Content-Type": "application/json"}
    if api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    payload = {
        "model": model_name,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        res = await _post_with_retry(client, url, payload, headers)
        if res.status_code != 200:
            try:
                err_data = res.json()
                err_msg = err_data.get("error", {}).get("message") or res.text
            except Exception:
                err_msg = res.text
            raise RuntimeError(f"LLM Provider error (HTTP {res.status_code}): {err_msg}")

        data = res.json()

    try:
        choices = data.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            content = message.get("content") or ""
            if content.strip():
                return content.strip()
        raise RuntimeError(f"Empty or invalid response payload: {json.dumps(data)[:300]}")
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise e
        raise RuntimeError(f"Failed to parse response: {e}") from e


def load_canonical_structure() -> str:
    root = Path(__file__).resolve().parent.parent
    path = root / "data" / "canonical_prompt_structure.md"
    return path.read_text(encoding="utf-8")
