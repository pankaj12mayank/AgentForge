from __future__ import annotations

import hashlib
import os
import re
import secrets
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover - fallback for environments without cryptography
    Fernet = None
    InvalidToken = None
from prompt_generation.config import WRITABLE_DIR

DB_PATH = Path(os.getenv("PROMPT_GEN_DB_PATH", str(WRITABLE_DIR / "data" / "config.sqlite")))

_KEY_FILE = Path(os.getenv("PROMPT_GEN_KEY_FILE", str(WRITABLE_DIR / "data" / ".secret_key")))

# Provider Presets
PRESETS: Dict[str, Dict[str, str]] = {
    "Google Gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model_name": "gemini-2.5-flash",
    },
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "model_name": "gpt-4o-mini",
    },
    "Groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model_name": "llama-3.3-70b-versatile",
    },
    "OpenRouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model_name": "meta-llama/llama-3.3-70b-instruct",
    },
    "Custom": {
        "base_url": "http://127.0.0.1:8000/v1",
        "model_name": "default",
    },
}


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# --- API Key Encryption at Rest ---

def _get_secret_key() -> bytes:
    """Load or create the machine-local key used to encrypt API keys at rest."""
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes().strip()
    if Fernet is None:  # pragma: no cover
        raise RuntimeError("cryptography is required to store API keys securely.")
    key = Fernet.generate_key()
    _KEY_FILE.write_bytes(key)
    try:
        _KEY_FILE.chmod(0o600)
    except OSError:
        pass
    return key


def _encrypt_key(value: str) -> str:
    if not value or Fernet is None:
        return value
    return Fernet(_get_secret_key()).encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt_key(value: str) -> str:
    if not value or Fernet is None:
        return value
    if not value.startswith("gAAAA"):
        return value  # legacy plaintext (migrates on next save)
    try:
        return Fernet(_get_secret_key()).decrypt(value.encode("ascii")).decode("utf-8")
    except Exception:  # pragma: no cover - key rotated/mismatch
        return value


def init_db() -> None:
    """Initialize database tables for provider settings and the prompts library."""
    with _get_connection() as conn:
        # Settings table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                provider_name TEXT NOT NULL,
                base_url TEXT NOT NULL,
                model_name TEXT NOT NULL,
                api_key TEXT NOT NULL DEFAULT '',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Prompts library & versioning table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'General',
                role TEXT NOT NULL DEFAULT '',
                goal TEXT NOT NULL DEFAULT '',
                steps TEXT NOT NULL DEFAULT '',
                review TEXT NOT NULL DEFAULT '',
                output_format TEXT NOT NULL DEFAULT '',
                additional_context TEXT NOT NULL DEFAULT '',
                markdown_content TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                parent_id INTEGER NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Test Drive sandbox removed in v3.1 - drop legacy table if present
        conn.execute("DROP TABLE IF EXISTS test_drive_history")

        # Registered user accounts (multi-user auth)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Per-user data isolation: every prompt belongs to the account that
        # saved it. Existing rows (pre-multi-user installs) stay on a shared
        # "__default__" scope. Runtime-created data is never auto-deleted.
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(prompts)").fetchall()]
        if "username" not in cols:
            conn.execute("ALTER TABLE prompts ADD COLUMN username TEXT NOT NULL DEFAULT '__default__'")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_prompts_username ON prompts(username, updated_at DESC)"
        )

        conn.commit()

        # Seed default preset if settings table is empty
        cursor = conn.execute("SELECT COUNT(*) FROM settings")
        if cursor.fetchone()[0] == 0:
            default_provider = "Google Gemini"
            preset = PRESETS[default_provider]
            conn.execute(
                """
                INSERT INTO settings (id, provider_name, base_url, model_name, api_key)
                VALUES (1, ?, ?, ?, ?)
                """,
                (default_provider, preset["base_url"], preset["model_name"], ""),
            )
            conn.commit()


def mask_key(key: str) -> str:
    """Mask API key showing only first 4 and last 4 chars."""
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}...{key[-4:]}"


def get_db_health() -> Dict[str, Any]:
    """Quick database status report for the system health panel."""
    init_db()
    try:
        with _get_connection() as conn:
            settings_count = conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
            prompts_count = conn.execute("SELECT COUNT(*) FROM prompts").fetchone()[0]
        return {"ok": True, "settings_count": settings_count, "prompts_count": prompts_count}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_settings(masked: bool = False) -> Dict[str, Any]:
    """Retrieve active LLM provider settings."""
    init_db()
    with _get_connection() as conn:
        row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
        if not row:
            return {
                "provider_name": "Google Gemini",
                "base_url": PRESETS["Google Gemini"]["base_url"],
                "model_name": PRESETS["Google Gemini"]["model_name"],
                "api_key": "",
                "has_key": False,
            }
        data = dict(row)
        raw_key = data.get("api_key", "")
        decrypted_key = _decrypt_key(raw_key)
        data["has_key"] = bool(decrypted_key.strip())
        if masked:
            data["api_key"] = mask_key(decrypted_key)
        else:
            data["api_key"] = decrypted_key
        return data


def save_settings(provider_name: str, base_url: str, model_name: str, api_key: str) -> Dict[str, Any]:
    """Save LLM provider settings."""
    init_db()
    current = get_settings(masked=False)

    p_name = provider_name.strip() or "Custom"
    b_url = base_url.strip().rstrip("/")
    m_name = model_name.strip()
    new_key = api_key.strip()

    if not new_key or ("..." in new_key and new_key == mask_key(current["api_key"])):
        new_key = current["api_key"]

    with _get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO settings (id, provider_name, base_url, model_name, api_key, updated_at)
            VALUES (1, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (p_name, b_url, m_name, _encrypt_key(new_key)),
        )
        conn.commit()

    return get_settings(masked=True)


# --- PROMPT LIBRARY & VERSIONING FUNCTIONS ---

def save_prompt_item(
    title: str,
    category: str,
    role: str,
    goal: str,
    steps: str,
    review: str,
    output_format: str,
    additional_context: str,
    markdown_content: str,
    parent_id: Optional[int] = None,
    username: str = "__default__",
) -> Dict[str, Any]:
    """Save a prompt to the library or create a new version of an existing prompt.

    `username` scopes the prompt to a specific account; versioning only links
    prompts owned by the same account, so one user's history stays invisible to
    everyone else.
    """
    init_db()
    cat = category.strip() or "General"
    t_name = title.strip() or "Untitled Master Prompt"

    version = 1
    root_parent_id = parent_id

    if parent_id is not None:
        with _get_connection() as conn:
            parent = conn.execute(
                "SELECT * FROM prompts WHERE id = ? AND username = ?", (parent_id, username)
            ).fetchone()
            if parent:
                parent_dict = dict(parent)
                version = parent_dict["version"] + 1
                root_parent_id = parent_dict["parent_id"] or parent_dict["id"]

    with _get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO prompts (
                title, category, role, goal, steps, review, output_format,
                additional_context, markdown_content, version, parent_id,
                username, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                t_name,
                cat,
                role.strip(),
                goal.strip(),
                steps.strip(),
                review.strip(),
                output_format.strip(),
                additional_context.strip(),
                markdown_content.strip(),
                version,
                root_parent_id,
                username.strip() or "__default__",
            ),
        )
        conn.commit()
        new_id = cursor.lastrowid

    return get_prompt_by_id(new_id, username=username.strip() or "__default__")


def list_prompts(search: str = "", category: str = "", username: str = "__default__") -> List[Dict[str, Any]]:
    """List saved prompts with optional search and category filtering."""
    init_db()
    query = "SELECT * FROM prompts WHERE username = ?"
    params: List[Any] = [username.strip() or "__default__"]

    if search.strip():
        query += " AND (title LIKE ? OR role LIKE ? OR goal LIKE ? OR markdown_content LIKE ?)"
        s = f"%{search.strip()}%"
        params.extend([s, s, s, s])

    if category.strip() and category.strip() != "All":
        query += " AND category = ?"
        params.append(category.strip())

    query += " ORDER BY updated_at DESC"

    with _get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_prompt_by_id(prompt_id: int, username: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve a single prompt by ID.

    When `username` is provided the prompt must belong to that account,
    otherwise the lookup acts like a missing row (404) — no cross-user reads.
    """
    init_db()
    query = "SELECT * FROM prompts WHERE id = ?"
    params: List[Any] = [prompt_id]
    if username is not None:
        query += " AND username = ?"
        params.append(username.strip() or "__default__")
    with _get_connection() as conn:
        row = conn.execute(query, params).fetchone()
        if not row:
            raise KeyError(f"Prompt ID {prompt_id} not found.")
        return dict(row)


def get_prompt_versions(prompt_id: int, username: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all versions associated with a prompt family."""
    init_db()
    prompt = get_prompt_by_id(prompt_id, username=username)
    root_id = prompt["parent_id"] or prompt["id"]

    query = "SELECT * FROM prompts WHERE (id = ? OR parent_id = ?)"
    params: List[Any] = [root_id, root_id]
    if username is not None:
        query += " AND username = ?"
        params.append(username.strip() or "__default__")
    query += " ORDER BY version ASC"
    with _get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def delete_prompt_item(prompt_id: int, username: Optional[str] = None) -> bool:
    """Delete a prompt entry. Only the owning account can delete its prompts."""
    init_db()
    query = "DELETE FROM prompts WHERE id = ?"
    params: List[Any] = [prompt_id]
    if username is not None:
        query += " AND username = ?"
        params.append(username.strip() or "__default__")
    with _get_connection() as conn:
        conn.execute(query, params)
        conn.commit()
        return True


# --- User Accounts (multi-user auth) ---

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
_PBKDF2_ITERATIONS = 200_000


def validate_username(username: str) -> Optional[str]:
    """Return an error message if the username is invalid, else None."""
    if not username:
        return "Username is required."
    if not _USERNAME_RE.match(username):
        return "Username must be 3-32 characters using letters, numbers, dot, dash or underscore."
    return None


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITERATIONS
    )
    return f"{salt}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, _ = stored.split("$", 1)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITERATIONS
        )
        return hmac_compare(digest.hex(), stored.split("$", 1)[1])
    except Exception:
        return False


def hmac_compare(a: str, b: str) -> bool:
    try:
        return secrets.compare_digest(a.encode(), b.encode())
    except Exception:
        return False


def register_user(username: str, password: str) -> Dict[str, Any]:
    """Create a user account. Raises ValueError for invalid/duplicate usernames."""
    init_db()
    err = validate_username(username)
    if err:
        raise ValueError(err)
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    with _get_connection() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, _hash_password(password)),
            )
            conn.commit()
            return {"id": cur.lastrowid, "username": username}
        except sqlite3.IntegrityError:
            raise ValueError("That username is already taken.")


def verify_user(username: str, password: str) -> bool:
    try:
        init_db()
        with _get_connection() as conn:
            row = conn.execute("SELECT password_hash FROM users WHERE username = ?", (username,)).fetchone()
            if row is None:
                return False
            return _verify_password(password, row["password_hash"])
    except Exception:
        return False


def user_exists(username: str) -> bool:
    try:
        init_db()
        with _get_connection() as conn:
            row = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
            return row is not None
    except Exception:
        return False


def get_session_secret() -> bytes:
    """Machine-local random secret used to sign login session cookies.

    Reuses the existing `data/.secret_key` (created at first launch), so no
    extra config file is needed and cookies stay un-forgeable per machine.
    """
    if _KEY_FILE.exists():
        return hashlib.sha256(_KEY_FILE.read_bytes()).digest()
    return hashlib.sha256(b"agentforge-session-default").digest()
