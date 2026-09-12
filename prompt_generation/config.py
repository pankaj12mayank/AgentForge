import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Repo root (parent of `prompt_generation/`)
_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


def get_writable_dir() -> Path:
    """Where user data (SQLite, secret key) lives.

    In a frozen (built) EXE, __file__ points inside the temp extraction dir, so
    user data must live next to the EXE instead of being recreated each launch.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return _ROOT


WRITABLE_DIR = get_writable_dir()

PORT = int(os.getenv("PORT", "8765"))
# Bind host. 127.0.0.1 (local-only) by default; use 0.0.0.0 only for explicit LAN use.
HOST = os.getenv("HOST", "127.0.0.1")
# Auth is ON by default (both local and server require login).
# Disable only for rapid local debugging: APP_AUTH_OFF=1
APP_AUTH_OFF = os.getenv("APP_AUTH_OFF", "").strip().lower() in ("1", "true", "yes", "on")
# Single shared password mode (APP_AUTH_TOKEN=secret).
APP_AUTH_TOKEN = os.getenv("APP_AUTH_TOKEN", "").strip()
# Multi-user mode (register + per-user login) — default when auth is on.
# Takes priority over the single shared password above.
APP_AUTH_USERS = os.getenv("APP_AUTH_USERS", "").strip().lower() in ("1", "true", "yes", "on")
# Set by launch.py to actual bind port when PORT is busy
LISTEN_PORT = int(os.getenv("LISTEN_PORT", str(PORT)))