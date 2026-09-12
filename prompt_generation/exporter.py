from __future__ import annotations

import json
from typing import Any, Dict


def export_prompt(prompt_data: Dict[str, Any], fmt: str) -> Dict[str, Any]:
    """Export a master prompt into Markdown, JSON, YAML, LangChain, or CrewAI formats."""
    fmt = fmt.lower().strip()
    title = prompt_data.get("title", "Master Prompt")
    role = prompt_data.get("role", "")
    goal = prompt_data.get("goal", "")
    markdown_content = prompt_data.get("markdown_content", "")

    if fmt == "json":
        data = {
            "title": title,
            "category": prompt_data.get("category", "General"),
            "version": prompt_data.get("version", 1),
            "role": role,
            "goal": goal,
            "system_prompt": markdown_content,
            "metadata": {
                "steps": prompt_data.get("steps", ""),
                "review": prompt_data.get("review", ""),
                "output_format": prompt_data.get("output_format", ""),
            },
        }
        return {
            "format": "json",
            "filename": f"{_slugify(title)}.json",
            "mime": "application/json",
            "content": json.dumps(data, indent=2),
        }

    elif fmt == "yaml":
        yaml_lines = [
            f"# Master Prompt Specification: {title}",
            f"title: {_yaml_quote(title)}",
            f"category: {_yaml_quote(prompt_data.get('category', 'General'))}",
            f"version: {prompt_data.get('version', 1)}",
            f"role: {_yaml_quote(role)}",
            f"goal: {_yaml_quote(goal)}",
            "system_prompt: |",
        ]
        for line in markdown_content.splitlines():
            yaml_lines.append(f"  {line}")
        
        return {
            "format": "yaml",
            "filename": f"{_slugify(title)}.yaml",
            "mime": "text/yaml",
            "content": "\n".join(yaml_lines),
        }

    elif fmt == "langchain":
        template = '''# LangChain ChatPromptTemplate Setup for "[TITLE]"
# pip install langchain-core

from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

SYSTEM_PROMPT = """[MARKDOWN]"""

prompt = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT),
    HumanMessagePromptTemplate.from_template("{input}"),
])

# Usage:
# chain = prompt | llm
# response = chain.invoke({"input": "Your task input here"})
'''
        py_code = (
            template
            .replace("[TITLE]", _py_escape(title))
            .replace("[MARKDOWN]", _py_escape(markdown_content))
        )
        return {
            "format": "langchain",
            "filename": f"langchain_{_slugify(title)}.py",
            "mime": "text/x-python",
            "content": py_code.strip(),
        }

    elif fmt in ("crewai", "autogen"):
        template = '''# CrewAI / AutoGen Agent Setup for "[TITLE]"
# pip install crewai autogen

from crewai import Agent

agent = Agent(
    role="""[ROLE]""",
    goal="""[GOAL]""",
    backstory="""[MARKDOWN]""",
    verbose=True,
    allow_delegation=False,
)

# AutoGen Alternative:
# from autogen import AssistantAgent
# assistant = AssistantAgent(
#     name="[SLUG]",
#     system_message="<paste generated markdown here>"
# )
'''
        py_code = (
            template
            .replace("[TITLE]", _py_escape(title))
            .replace("[ROLE]", _py_escape(role or title))
            .replace("[GOAL]", _py_escape(goal or "Execute tasks according to system prompt specifications."))
            .replace("[MARKDOWN]", _py_escape(markdown_content))
            .replace("[SLUG]", _slugify(title))
        )
        return {
            "format": "crewai",
            "filename": f"agent_{_slugify(title)}.py",
            "mime": "text/x-python",
            "content": py_code.strip(),
        }

    else:
        # Default Markdown
        return {
            "format": "markdown",
            "filename": f"{_slugify(title)}.md",
            "mime": "text/markdown",
            "content": markdown_content,
        }


def _slugify(text: str) -> str:
    cleaned = "".join(c if c.isalnum() else "_" for c in text.lower())
    return "_".join(filter(None, cleaned.split("_"))) or "master_prompt"


def _py_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"').replace("{", "{{").replace("}", "}}")


def _yaml_quote(text: str) -> str:
    escaped = text.replace('"', '\\"')
    return f'"{escaped}"'
