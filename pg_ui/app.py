from __future__ import annotations

import hashlib
import hmac
import sys
import time
from pathlib import Path
from typing import Optional

# Repo root on sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from prompt_generation.builder import RoughInput, generate_master_prompt
from prompt_generation.config import APP_AUTH_OFF, APP_AUTH_TOKEN, APP_AUTH_USERS, HOST, LISTEN_PORT, PORT
from prompt_generation.db import (
    PRESETS,
    delete_prompt_item,
    get_prompt_by_id,
    get_prompt_versions,
    get_session_secret,
    get_settings,
    list_prompts,
    register_user,
    save_prompt_item,
    save_settings,
    user_exists,
    validate_username,
    verify_user,
)
from prompt_generation.diff_engine import compute_prompt_diff
from prompt_generation.exporter import export_prompt
from prompt_generation.health import get_system_health
from prompt_generation.llm_client import fetch_provider_models, test_provider_connection
from prompt_generation.orchestrator import generate_multi_agent_suite
from prompt_generation.ratelimit import rate_limit_high

app = FastAPI(title="AgentForge", version="3.1.0")

_APIS_SCHEME = "Bearer"

# --- Session helpers (login for web/deployed use) ---

_SESSION_COOKIE = "agentforge_sid"
_SESSION_HOURS = 24 * 30  # 30 days


def _auth_mode() -> str:
    """users = register + per-user login (default) | password = one shared password | off"""
    if APP_AUTH_OFF:
        return "off"
    if APP_AUTH_USERS:
        return "users"
    if APP_AUTH_TOKEN.strip():
        return "password"
    return "users"


def _auth_enabled() -> bool:
    return _auth_mode() != "off"


def _issue_sid(user: str = "") -> str:
    ts = str(int(time.time()))
    exp = str(int(time.time()) + _SESSION_HOURS * 3600)
    payload = f"{user}|{ts}|{exp}"
    sig = hmac.new(get_session_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{sig}"


def _sid_valid(cookie: str) -> bool:
    try:
        user, ts, exp, sig = cookie.split("|")
        if int(time.time()) > int(exp):
            return False
        expected = hmac.new(get_session_secret(), f"{user}|{ts}|{exp}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)
    except Exception:
        return False


def _set_session_cookie(resp: Response, request: Request, user: str = "") -> None:
    resp.set_cookie(
        _SESSION_COOKIE,
        _issue_sid(user),
        max_age=_SESSION_HOURS * 3600,
        path="/",
        httponly=True,
        samesite="lax",
        secure=(request.url.scheme == "https"),
    )


def _current_username(request: Request) -> str:
    """Account namespace for the current request.

    In users mode it's the signed-in username; password mode and the open
    (auth-off) local install share a "__default__" namespace. The middleware
    already guarantees the session cookie is valid whenever this is reached.
    """
    if _auth_mode() != "users":
        return "__default__"
    cookie = request.cookies.get(_SESSION_COOKIE, "")
    user, *_rest = cookie.split("|")
    return user or "__default__"


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Full app gate when auth is on: login/register pages + session cookie.

    Local mode (auth off) skips everything. Web/deployed mode protects the UI,
    /api/*, static assets and the app shell alike.
    """
    mode = _auth_mode()
    if mode == "off":
        return await call_next(request)

    path = request.url.path

    # Always reachable: auth pages, auth endpoints, icons and static assets.
    if (
        path in ("/login", "/api/login", "/signup", "/api/register", "/logout",
                 "/favicon.ico", "/favicon.svg")
        or path.startswith("/static/")
        or path in ("/sw.js", "/manifest.webmanifest")
    ):
        return await call_next(request)

    # Authenticated via browser session cookie.
    if _sid_valid(request.cookies.get(_SESSION_COOKIE, "")):
        return await call_next(request)

    # Script/API clients may use the shared Bearer token in password mode.
    if mode == "password" and path.startswith("/api/"):
        provided = request.headers.get("Authorization", "")
        if hmac.compare_digest(provided, f"{_APIS_SCHEME} {APP_AUTH_TOKEN}"):
            return await call_next(request)
        return JSONResponse({"ok": False, "detail": "Unauthorized"}, status_code=401)

    # Any other /api request from an unauthenticated session.
    if path.startswith("/api/"):
        return JSONResponse({"ok": False, "detail": "Unauthorized"}, status_code=401)

    # Browser navigation without a session -> login page.
    return RedirectResponse("/login", status_code=302)

_static = Path(__file__).parent / "static"
_templates = Path(__file__).parent / "templates"
if _static.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static)), name="static")
templates = Jinja2Templates(directory=str(_templates))


# --- Request Models ---

class GenerateBody(BaseModel):
    role: str = Field(default="", max_length=1000)
    goal: str = Field(default="", max_length=5000)
    steps: str = Field(default="", max_length=10000)
    review: str = Field(default="", max_length=5000)
    output: str = Field(default="", max_length=5000)
    additional_context: str = Field(default="", max_length=16000)


class SettingsBody(BaseModel):
    provider_name: str = Field(..., max_length=100)
    base_url: str = Field(..., max_length=500)
    model_name: str = Field(..., max_length=100)
    api_key: str = Field(default="", max_length=1000)


class TestConnectionBody(BaseModel):
    provider_name: str = Field(default="Custom", max_length=100)
    base_url: str = Field(..., max_length=500)
    model_name: str = Field(..., max_length=100)
    api_key: str = Field(default="", max_length=1000)


class FetchModelsBody(BaseModel):
    base_url: str = Field(..., max_length=500)
    api_key: str = Field(default="", max_length=1000)


class SavePromptBody(BaseModel):
    title: str = Field(..., max_length=200)
    category: str = Field(default="General", max_length=100)
    role: str = Field(default="")
    goal: str = Field(default="")
    steps: str = Field(default="")
    review: str = Field(default="")
    output_format: str = Field(default="")
    additional_context: str = Field(default="")
    markdown_content: str = Field(...)
    parent_id: Optional[int] = Field(default=None)


class OrchestrateBody(BaseModel):
    project_title: str = Field(...)
    objective: str = Field(...)
    tech_stack: str = Field(default="")


class DiffBody(BaseModel):
    id_a: int = Field(...)
    id_b: int = Field(...)


class ExportBody(BaseModel):
    title: str = Field(default="Master Prompt", max_length=200)
    category: str = Field(default="General", max_length=100)
    role: str = Field(default="")
    goal: str = Field(default="")
    steps: str = Field(default="")
    review: str = Field(default="")
    output_format: str = Field(default="")
    markdown_content: str = Field(...)
    format: str = Field(default="markdown")  # json, yaml, langchain, crewai, markdown


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    settings = get_settings(masked=True)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "settings": settings,
            "presets": PRESETS,
            "auth_enabled": _auth_enabled(),
        },
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    mode = _auth_mode()
    if _sid_valid(request.cookies.get(_SESSION_COOKIE, "")):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"auth_enabled": _auth_enabled(), "mode": mode},
    )


@app.post("/api/login")
async def login(request: Request) -> JSONResponse:
    mode = _auth_mode()
    if mode == "off":
        return JSONResponse({"ok": True, "redirect": "/"})
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body.")
    if mode == "password":
        provided = str(body.get("password", ""))
        if not hmac.compare_digest(provided, APP_AUTH_TOKEN):
            return JSONResponse({"ok": False, "detail": "Wrong password."}, status_code=401)
        resp = JSONResponse({"ok": True, "redirect": "/"})
        _set_session_cookie(resp, request)
        return resp
    # users mode
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    if not verify_user(username, password):
        return JSONResponse({"ok": False, "detail": "Wrong username or password."}, status_code=401)
    resp = JSONResponse({"ok": True, "redirect": "/"})
    _set_session_cookie(resp, request, user=username)
    return resp


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    if _auth_mode() == "off":
        return RedirectResponse("/", status_code=302)
    if _sid_valid(request.cookies.get(_SESSION_COOKIE, "")):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        request,
        "signup.html",
        {"auth_enabled": _auth_enabled()},
    )


@app.post("/api/register")
async def register(request: Request) -> JSONResponse:
    if _auth_mode() != "users":
        return JSONResponse({"ok": False, "detail": "Registration is disabled."}, status_code=403)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body.")
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))
    try:
        register_user(username, password)
    except ValueError as exc:
        return JSONResponse({"ok": False, "detail": str(exc)}, status_code=400)
    resp = JSONResponse({"ok": True, "redirect": "/"})
    _set_session_cookie(resp, request, user=username)
    return resp


@app.get("/logout")
async def logout() -> RedirectResponse:
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie(_SESSION_COOKIE, path="/")
    return resp


@app.get("/favicon.ico")
async def favicon_ico() -> Response:
    favicon = _static / "favicon.ico"
    if favicon.is_file():
        return Response(content=favicon.read_bytes(), media_type="image/x-icon")
    return Response(content=b"", status_code=204)


@app.get("/favicon.svg")
async def favicon_svg() -> Response:
    favicon = _static / "favicon.svg"
    if favicon.is_file():
        return Response(content=favicon.read_bytes(), media_type="image/svg+xml")
    return Response(content=b"", status_code=404)


@app.get("/manifest.webmanifest")
async def webmanifest() -> Response:
    manifest = _static / "manifest.webmanifest"
    if manifest.is_file():
        return Response(content=manifest.read_bytes(), media_type="application/manifest+json")
    return Response(content=b"{}", status_code=404)


@app.get("/sw.js")
async def service_worker() -> Response:
    sw = _static / "sw.js"
    if sw.is_file():
        return Response(content=sw.read_bytes(), media_type="text/javascript", headers={"Cache-Control": "no-cache"})
    return Response(content=b"", status_code=404)


@app.get("/api/settings")
async def fetch_settings() -> JSONResponse:
    settings = get_settings(masked=True)
    return JSONResponse({"ok": True, "settings": settings, "presets": PRESETS})


@app.post("/api/settings")
async def update_settings(body: SettingsBody) -> JSONResponse:
    updated = save_settings(
        provider_name=body.provider_name,
        base_url=body.base_url,
        model_name=body.model_name,
        api_key=body.api_key,
    )
    return JSONResponse({"ok": True, "message": "Settings saved successfully!", "settings": updated})


@app.post("/api/models/fetch", dependencies=[Depends(rate_limit_high)])
async def fetch_models(body: FetchModelsBody) -> JSONResponse:
    raw_key = body.api_key.strip()
    current = get_settings(masked=False)

    if not raw_key or ("..." in raw_key and raw_key == get_settings(masked=True).get("api_key")):
        raw_key = current.get("api_key", "")

    res = await fetch_provider_models(
        base_url=body.base_url,
        api_key=raw_key,
    )
    return JSONResponse(res)


@app.post("/api/settings/test", dependencies=[Depends(rate_limit_high)])
async def test_settings(body: TestConnectionBody) -> JSONResponse:
    raw_key = body.api_key.strip()
    current = get_settings(masked=False)

    if not raw_key or ("..." in raw_key and raw_key == get_settings(masked=True).get("api_key")):
        raw_key = current.get("api_key", "")

    res = await test_provider_connection(
        base_url=body.base_url,
        model_name=body.model_name,
        api_key=raw_key,
        provider_name=body.provider_name,
    )
    return JSONResponse(res)


@app.get("/api/health")
async def health() -> JSONResponse:
    settings = get_settings(masked=True)
    system = get_system_health()
    return JSONResponse(
        {
            "ok": True,
            "provider_configured": settings.get("has_key", False),
            "provider_name": settings.get("provider_name", ""),
            "model_name": settings.get("model_name", ""),
            "settings": settings,
            "app_port": LISTEN_PORT,
            "configured_port": PORT,
            "bind_host": HOST,
            "system": system,
        }
    )


@app.post("/api/generate", dependencies=[Depends(rate_limit_high)])
async def generate(body: GenerateBody) -> JSONResponse:
    if not any(
        [
            body.role.strip(),
            body.goal.strip(),
            body.steps.strip(),
        ]
    ):
        raise HTTPException(
            status_code=400,
            detail="Provide at least Role, Goal, or Steps to generate a prompt.",
        )
    rough = RoughInput(
        role=body.role.strip(),
        goal=body.goal.strip(),
        steps=body.steps.strip(),
        review=body.review.strip(),
        output=body.output.strip(),
        additional_context=body.additional_context.strip(),
    )
    try:
        markdown = await generate_master_prompt(rough)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM Provider error: {e}") from e
    return JSONResponse({"markdown": markdown})


# --- PROMPT LIBRARY ENDPOINTS ---

@app.get("/api/prompts")
async def get_prompts_list(request: Request, search: str = "", category: str = "") -> JSONResponse:
    prompts = list_prompts(search=search, category=category, username=_current_username(request))
    return JSONResponse({"ok": True, "prompts": prompts})


@app.post("/api/prompts/save")
async def save_prompt(request: Request, body: SavePromptBody) -> JSONResponse:
    try:
        saved = save_prompt_item(
            title=body.title,
            category=body.category,
            role=body.role,
            goal=body.goal,
            steps=body.steps,
            review=body.review,
            output_format=body.output_format,
            additional_context=body.additional_context,
            markdown_content=body.markdown_content,
            parent_id=body.parent_id,
            username=_current_username(request),
        )
        return JSONResponse({"ok": True, "message": f"Prompt '{saved['title']}' (v{saved['version']}) saved!", "prompt": saved})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save prompt: {e}") from e


@app.get("/api/prompts/{prompt_id}")
async def get_single_prompt(request: Request, prompt_id: int) -> JSONResponse:
    try:
        prompt = get_prompt_by_id(prompt_id, username=_current_username(request))
        return JSONResponse({"ok": True, "prompt": prompt})
    except KeyError:
        raise HTTPException(status_code=404, detail="Prompt not found")


@app.get("/api/prompts/{prompt_id}/versions")
async def get_versions(request: Request, prompt_id: int) -> JSONResponse:
    try:
        versions = get_prompt_versions(prompt_id, username=_current_username(request))
        return JSONResponse({"ok": True, "versions": versions})
    except KeyError:
        raise HTTPException(status_code=404, detail="Prompt not found")


@app.delete("/api/prompts/{prompt_id}")
async def delete_prompt(request: Request, prompt_id: int) -> JSONResponse:
    delete_prompt_item(prompt_id, username=_current_username(request))
    return JSONResponse({"ok": True, "message": "Prompt deleted."})


# --- MULTI-AGENT ORCHESTRATOR ---

@app.post("/api/orchestrate", dependencies=[Depends(rate_limit_high)])
async def orchestrate_suite(body: OrchestrateBody) -> JSONResponse:
    try:
        suite = await generate_multi_agent_suite(
            project_title=body.project_title,
            objective=body.objective,
            tech_stack=body.tech_stack,
        )
        return JSONResponse({"ok": True, "suite": suite})
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Orchestration error: {e}") from e


# --- DIFF ENGINE ---

@app.post("/api/prompts/diff")
async def compute_diff(request: Request, body: DiffBody) -> JSONResponse:
    try:
        user = _current_username(request)
        prompt_a = get_prompt_by_id(body.id_a, username=user)
        prompt_b = get_prompt_by_id(body.id_b, username=user)

        title_a = f"{prompt_a['title']} (v{prompt_a['version']})"
        title_b = f"{prompt_b['title']} (v{prompt_b['version']})"

        diff_res = compute_prompt_diff(
            text_a=prompt_a["markdown_content"],
            text_b=prompt_b["markdown_content"],
            title_a=title_a,
            title_b=title_b,
        )
        return JSONResponse({"ok": True, "diff": diff_res})
    except KeyError:
        raise HTTPException(status_code=404, detail="One or both prompts not found.")


# --- MULTI-FORMAT EXPORT ---

@app.post("/api/export")
async def export_prompt_format(body: ExportBody) -> JSONResponse:
    prompt_data = body.model_dump()
    exported = export_prompt(prompt_data, fmt=body.format)
    return JSONResponse({"ok": True, "export": exported})
