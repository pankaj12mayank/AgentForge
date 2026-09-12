from __future__ import annotations

from dataclasses import dataclass

from prompt_generation.llm_client import generate_chat_completion, load_canonical_structure


@dataclass
class RoughInput:
    role: str
    goal: str
    steps: str
    review: str
    output: str
    additional_context: str

    def to_user_block(self) -> str:
        lines = [
            "## Structured prompt details",
            "",
            f"1. Role: {self.role or '(not provided)'}",
            f"2. Goal: {self.goal or '(not provided)'}",
            f"3. Steps: {self.steps or '(not provided)'}",
            f"4. After Execution Review: {self.review or '(not provided)'}",
            f"5. Output format: {self.output or '(not provided)'}",
            "",
            "## Additional context",
            "",
            self.additional_context.strip() or "(none)",
        ]
        return "\n".join(lines)


def build_system_prompt(canonical: str) -> str:
    return f"""You are a Master Prompt Engineer.

Your task: Create a 100% accurate, highly effective master prompt for an AI agent based on the provided details.

CRITICAL RULES (structure fidelity):
1. The generated prompt MUST have these sections in order: ROLE, GOAL, PROCESS STEPS, AFTER EXECUTION REVIEW, and OUTPUT FORMAT.
2. Use the CANONICAL STRUCTURE below as a baseline for the layout, but prioritize the specific user inputs provided.
3. If the user provided specific steps, use them exactly. If they are vague, expand them into professional, executable instructions.
4. The 'AFTER EXECUTION REVIEW' section should include automated self-checks for the agent to ensure high-quality output.
5. No AI-hype, no emojis, no preamble. Just the final Markdown document.

CANONICAL STRUCTURE (Baseline):

{canonical}
"""


async def generate_master_prompt(rough: RoughInput) -> str:
    canonical = load_canonical_structure()
    system = build_system_prompt(canonical)
    user = (
        rough.to_user_block()
        + "\n\nGenerate the full master prompt Markdown now, following all CRITICAL RULES."
    )
    return await generate_chat_completion(system, user, temperature=0.15)
