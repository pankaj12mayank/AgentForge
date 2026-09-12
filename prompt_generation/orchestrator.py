from __future__ import annotations

from typing import Any, Dict, List

from prompt_generation.llm_client import generate_chat_completion


async def generate_multi_agent_suite(project_title: str, objective: str, tech_stack: str = "") -> Dict[str, Any]:
    """Generate a coordinated 3-agent prompt suite (Architect, Developer, QA Auditor) for a project."""
    title = project_title.strip() or "Enterprise Project"
    obj = objective.strip() or "Build scalable software solution"
    stack = tech_stack.strip() or "Standard Stack"

    system_prompt = """You are a Lead AI Systems Architect specializing in multi-agent orchestration.

Your task: Generate a coordinated 3-agent master prompt suite for an automated AI team.

ROLES TO GENERATE:
1. Agent 1: System Architect Agent (High-level system design, schema, and API contracts)
2. Agent 2: Senior Developer Agent (Implementation, clean code execution, and refactoring)
3. Agent 3: QA & Security Auditor Agent (Code audit, test coverage, and OWASP compliance)

CRITICAL INSTRUCTIONS:
- Each agent prompt MUST strictly follow this structure: ROLE, GOAL, PROCESS STEPS, AFTER EXECUTION REVIEW, and OUTPUT FORMAT.
- Ensure the 3 agents have clear input/output compatibility so Agent 1 outputs feed into Agent 2, and Agent 2 outputs feed into Agent 3.
- Output MUST be valid JSON matching this exact structure:
{
  "project": "...",
  "suite": [
    {
      "agent_num": 1,
      "agent_name": "System Architect Agent",
      "role": "...",
      "goal": "...",
      "markdown_prompt": "FULL_MARKDOWN_SYSTEM_PROMPT_1"
    },
    {
      "agent_num": 2,
      "agent_name": "Senior Developer Agent",
      "role": "...",
      "goal": "...",
      "markdown_prompt": "FULL_MARKDOWN_SYSTEM_PROMPT_2"
    },
    {
      "agent_num": 3,
      "agent_name": "QA & Security Auditor Agent",
      "role": "...",
      "goal": "...",
      "markdown_prompt": "FULL_MARKDOWN_SYSTEM_PROMPT_3"
    }
  ]
}
No preamble, no markdown backticks surrounding the JSON if possible, just clean JSON.
"""

    user_prompt = f"""Project Title: {title}
Business Objective: {obj}
Tech Stack / Context: {stack}

Generate the 3-agent prompt suite JSON now."""

    raw_resp = await generate_chat_completion(system_prompt, user_prompt, temperature=0.2)

    import json
    # Strip potential ```json wrappers if returned by LLM
    clean_text = raw_resp.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    if clean_text.startswith("```"):
        clean_text = clean_text[3:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]
    clean_text = clean_text.strip()

    try:
        data = json.loads(clean_text)
        if isinstance(data, dict) and isinstance(data.get("suite"), list):
            return data
        raise ValueError("suite key missing or malformed")
    except Exception:
        defaults = [
            (1, "System Architect Agent", "System Architect"),
            (2, "Senior Developer Agent", "Senior Developer"),
            (3, "QA & Security Auditor Agent", "QA & Security Auditor"),
        ]
        return {
            "project": title,
            "suite": [
                {
                    "agent_num": num,
                    "agent_name": name,
                    "role": role,
                    "goal": f"{role_name} for {title}",
                    "markdown_prompt": raw_resp if num == 1 else (
                        f"# {name}\n\nGoal: {role_name} for {title}\n"
                        f"Raw LLM output could not be parsed as JSON; full response:\n\n{raw_resp}"
                    ),
                }
                for num, name, role_name in defaults
            ],
            "parse_warning": "LLM returned non-JSON; suite built from defaults.",
        }
