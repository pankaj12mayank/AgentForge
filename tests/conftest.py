import os
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_TMP = Path(tempfile.mkdtemp(prefix="pg_test_"))
os.environ["PROMPT_GEN_DB_PATH"] = str(_TMP / "config.sqlite")
os.environ["PROMPT_GEN_KEY_FILE"] = str(_TMP / ".secret_key")
os.environ["APP_AUTH_TOKEN"] = ""
os.environ["APP_AUTH_USERS"] = ""
os.environ["APP_AUTH_OFF"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from pg_ui.app import app  # noqa: E402
from prompt_generation import db  # noqa: E402
from prompt_generation import ratelimit  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_db():
    db.init_db()
    with db._get_connection() as conn:
        conn.execute("DELETE FROM settings")
        conn.execute("DELETE FROM prompts")
        conn.execute("DELETE FROM users")
        conn.commit()
    yield
    with db._get_connection() as conn:
        conn.execute("DELETE FROM settings")
        conn.execute("DELETE FROM prompts")
        conn.execute("DELETE FROM users")
        conn.commit()


@pytest.fixture()
def saved_prompt_id() -> int:
    row = db.save_prompt_item(
        title="API Test Prompt",
        category="Testing",
        role="Engineer",
        goal="Build test suite",
        steps="1. Write tests\n2. Run them",
        review="Check coverage",
        output_format="Markdown",
        additional_context="nothing extra",
        markdown_content="# Master Prompt",
    )
    return row["id"]