import pytest

from prompt_generation import db


def test_settings_roundtrip_encrypted():
    saved = db.save_settings(
        provider_name="OpenAI",
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o-mini",
        api_key="sk-SuperSecretKeyValue",
    )
    assert saved["has_key"] is True
    assert "SuperSecretKeyValue" not in saved["api_key"]

    raw = db.get_settings(masked=False)
    assert raw["api_key"] == "sk-SuperSecretKeyValue"

    masked = db.get_settings(masked=True)
    assert masked["api_key"] == "sk-S...alue"


def test_legacy_plaintext_key_can_be_read():
    with db._get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (id, provider_name, base_url, model_name, api_key) "
            "VALUES (1, 'Nvidia', 'https://integrate.api.nvidia.com/v1', 'nvidia/test', ?)",
            ("nvapi-legacy-plaintext-key",),
        )
        conn.commit()

    raw = db.get_settings(masked=False)
    assert raw["api_key"] == "nvapi-legacy-plaintext-key"
    assert raw["has_key"] is True


def test_save_prompt_returns_id_and_version():
    row = db.save_prompt_item(
        title="First",
        category="General",
        role="Dev",
        goal="",
        steps="",
        review="",
        output_format="",
        additional_context="",
        markdown_content="# A",
    )
    assert row["version"] == 1
    assert row["title"] == "First"


def test_prompt_versioning_family():
    a = db.save_prompt_item(
        title="Prompt", category="Gen", role="", goal="", steps="", review="",
        output_format="", additional_context="", markdown_content="# v1",
    )
    b = db.save_prompt_item(
        title="Prompt", category="Gen", role="", goal="", steps="", review="",
        output_format="", additional_context="", markdown_content="# v2",
        parent_id=a["id"],
    )
    versions = db.get_prompt_versions(a["id"])
    assert [v["version"] for v in versions] == [1, 2]
    assert versions[0]["parent_id"] is None
    assert versions[1]["parent_id"] == a["id"]


def test_list_prompts_search_and_category(saved_prompt_id):
    rows = db.list_prompts(search="Build test")
    assert rows and rows[0]["id"] == saved_prompt_id

    rows = db.list_prompts(category="Testing")
    assert rows and rows[0]["id"] == saved_prompt_id

    rows = db.list_prompts(category="Nothing")
    assert rows == []


def test_delete_prompt_raises_keyerror(saved_prompt_id):
    db.delete_prompt_item(saved_prompt_id)
    with pytest.raises(KeyError):
        db.get_prompt_by_id(saved_prompt_id)