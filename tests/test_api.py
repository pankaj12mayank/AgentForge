import uuid

import pytest

import pg_ui.app as pg_app
from prompt_generation import ratelimit

BASE = {
    "title": "Gen",
    "category": "General",
    "version": 1,
    "role": "Engineer",
    "goal": "Ship it",
    "steps": "Write code",
    "review": "Review it",
    "output_format": "Markdown",
    "markdown_content": "# Role",
}


def test_health_returns_without_llm_call(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert "provider_configured" in data
    assert "app_port" in data
    assert "bind_host" in data


def test_generate_requires_fields(client):
    r = client.post("/api/generate", json={})
    assert r.status_code == 400


def test_save_and_get_prompt_via_api(client):
    payload = {
        "title": "From API",
        "category": "API",
        "markdown_content": "# Master",
        "role": "Dev",
        "goal": "Goal",
        "steps": "Steps",
        "review": "",
        "output_format": "",
        "additional_context": "",
        "parent_id": None,
    }
    r = client.post("/api/prompts/save", json=payload)
    assert r.status_code == 200
    pid = r.json()["prompt"]["id"]

    r = client.get(f"/api/prompts/{pid}")
    assert r.status_code == 200
    assert r.json()["prompt"]["role"] == "Dev"

    r = client.get("/api/prompts?search=From API")
    assert r.status_code == 200
    assert len(r.json()["prompts"]) == 1


def test_prompt_404(client):
    r = client.get("/api/prompts/999999")
    assert r.status_code == 404


def test_export_endpoint(client):
    payload = {**BASE, "format": "json"}
    r = client.post("/api/export", json=payload)
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_default_auth_is_users_mode(monkeypatch, client):
    """Auth defaults to users mode (register + login) when no env vars are set."""
    monkeypatch.setattr(pg_app, "APP_AUTH_OFF", False)
    monkeypatch.setattr(pg_app, "APP_AUTH_USERS", False)
    monkeypatch.setattr(pg_app, "APP_AUTH_TOKEN", "")
    assert pg_app._auth_mode() == "users"
    # `/` redirects to login when no session exists.
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 303)
    assert r.headers["location"] == "/login"


def test_auth_middleware_enforced(monkeypatch, client):
    from fastapi.testclient import TestClient

    monkeypatch.setattr(pg_app, "APP_AUTH_OFF", False)
    monkeypatch.setattr(pg_app, "APP_AUTH_TOKEN", "sekrit")

    # No credentials -> API rejected, browser redirected to the login page.
    assert client.get("/api/health").status_code == 401
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/login"

    # Wrong password rejected.
    assert client.post("/api/login", json={"password": "nope"}).status_code == 401

    # Successful login issues a session cookie that unlocks the whole app.
    r = client.post("/api/login", json={"password": "sekrit"})
    assert r.status_code == 200
    assert r.json().get("redirect") == "/"
    assert client.get("/api/health").status_code == 200
    r = client.get("/")
    assert r.status_code == 200
    assert 'data-auth="true"' in r.text

    # Bearer token still works for script/API clients.
    with TestClient(pg_app.app) as c2:
        assert c2.get("/api/health", headers={"Authorization": "Bearer sekrit"}).status_code == 200
        assert c2.get("/", follow_redirects=False).status_code == 302


def test_multiuser_register_login(monkeypatch, client):
    monkeypatch.setattr(pg_app, "APP_AUTH_OFF", False)
    monkeypatch.setattr(pg_app, "APP_AUTH_USERS", True)
    uname = f"user_{uuid.uuid4().hex[:8]}"
    pw = "StrongPass123"

    # Unauthenticated: UI redirects to login, signup page reachable.
    assert client.get("/", follow_redirects=False).status_code == 302
    assert client.get("/login").status_code == 200
    assert client.get("/signup").status_code == 200

    # Register once, duplicate rejected, invalid username rejected.
    assert client.post("/api/register", json={"username": uname, "password": pw}).status_code == 200
    assert client.post("/api/register", json={"username": uname, "password": "Another123"}).status_code == 400
    assert client.post("/api/register", json={"username": "ab", "password": "LongPass123"}).status_code == 400

    # Wrong password rejected.
    assert client.post("/api/login", json={"username": uname, "password": "wrong"}).status_code == 401

    # Correct login unlocks the whole app.
    r = client.post("/api/login", json={"username": uname, "password": pw})
    assert r.status_code == 200
    assert client.get("/api/health").status_code == 200
    assert client.get("/").status_code == 200
    assert 'data-auth="true"' in client.get("/").text


def test_multiuser_data_isolation(monkeypatch, client):
    """Each account only sees/edits its own prompts (no cross-user leaks)."""
    monkeypatch.setattr(pg_app, "APP_AUTH_OFF", False)
    monkeypatch.setattr(pg_app, "APP_AUTH_USERS", True)
    u1 = f"u1_{uuid.uuid4().hex[:8]}"
    u2 = f"u2_{uuid.uuid4().hex[:8]}"
    pw = "StrongPass123"

    assert client.post("/api/register", json={"username": u1, "password": pw}).status_code == 200
    assert client.post("/api/register", json={"username": u2, "password": pw}).status_code == 200

    # u2 saves a prompt.
    assert client.post("/api/login", json={"username": u2, "password": pw}).status_code == 200
    r = client.post("/api/prompts/save", json={**BASE, "title": "User2 Secret"})
    assert r.status_code == 200
    pid = r.json()["prompt"]["id"]
    r = client.get("/api/prompts")
    assert [p["title"] for p in r.json()["prompts"]] == ["User2 Secret"]

    # u1 logs in: the other account's prompt is fully invisible.
    assert client.get("/logout", follow_redirects=False).status_code in (302, 303)
    assert client.post("/api/login", json={"username": u1, "password": pw}).status_code == 200
    assert client.get("/api/prompts").json()["prompts"] == []
    assert client.get(f"/api/prompts/{pid}").status_code == 404
    assert client.get(f"/api/prompts/{pid}/versions").status_code == 404
    # Delete is scoped: u1's delete call cannot remove u2's prompt.
    assert client.delete(f"/api/prompts/{pid}").status_code == 200

    # u2's data is still intact afterwards.
    assert client.get("/logout", follow_redirects=False).status_code in (302, 303)
    assert client.post("/api/login", json={"username": u2, "password": pw}).status_code == 200
    r = client.get("/api/prompts")
    assert [p["title"] for p in r.json()["prompts"]] == ["User2 Secret"]


def test_rate_limiter_blocks_after_limit():
    class FakeRequest:
        client = type("C", (), {"host": "1.2.3.4"})()

    for _ in range(ratelimit._DEFAULT_LIMIT):
        ratelimit._check(FakeRequest, limit=ratelimit._DEFAULT_LIMIT, window=60.0)

    with pytest.raises(Exception) as exc_info:
        ratelimit._check(FakeRequest, limit=ratelimit._DEFAULT_LIMIT, window=60.0)
    assert exc_info.value.status_code == 429
