from __future__ import annotations

import difflib
from typing import Any, Dict, List


def compute_prompt_diff(text_a: str, text_b: str, title_a: str = "Version A", title_b: str = "Version B") -> Dict[str, Any]:
    """Compute line-by-line diff between two text versions."""
    lines_a = text_a.splitlines()
    lines_b = text_b.splitlines()

    differ = difflib.Differ()
    diff_results: List[Dict[str, Any]] = []

    additions = 0
    deletions = 0
    unchanged = 0

    for line in differ.compare(lines_a, lines_b):
        code = line[:2]
        content = line[2:]

        if code == "+ ":
            additions += 1
            diff_results.append({"type": "add", "content": content})
        elif code == "- ":
            deletions += 1
            diff_results.append({"type": "delete", "content": content})
        elif code == "  ":
            unchanged += 1
            diff_results.append({"type": "equal", "content": content})

    return {
        "title_a": title_a,
        "title_b": title_b,
        "stats": {
            "additions": additions,
            "deletions": deletions,
            "unchanged": unchanged,
            "total_changes": additions + deletions,
        },
        "lines": diff_results,
    }
