from prompt_generation.exporter import export_prompt

BASE = {
    "title": 'Test "Quoted" Prompt',
    "category": "General",
    "version": 2,
    "role": "Engineer",
    "goal": "Ship it",
    "steps": "Write code",
    "review": "Review it",
    "output_format": "Markdown",
    "markdown_content": '# Role\n\nTriple """ quote {and braces} here\n',
}


def test_export_json_valid():
    out = export_prompt(BASE, "json")
    assert out["format"] == "json"
    assert '"title": "Test \\"Quoted\\" Prompt"' in out["content"]


def test_export_markdown_default():
    out = export_prompt(BASE, "markdown")
    assert out["format"] == "markdown"
    assert out["content"] == BASE["markdown_content"]


def test_langchain_escape_compiles():
    out = export_prompt(BASE, "langchain")
    compile(out["content"], "<langchain>", "exec")


def test_crewai_escape_compiles():
    out = export_prompt(BASE, "crewai")
    compiled = compile(out["content"], "<crewai>", "exec")
    assert compiled is not None