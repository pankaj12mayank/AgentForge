from prompt_generation.diff_engine import compute_prompt_diff


def test_diff_stats_counts_lines():
    res = compute_prompt_diff("a\nb\nc", "a\nx\nc", "v1", "v2")
    assert res["title_a"] == "v1"
    assert res["title_b"] == "v2"
    assert res["stats"]["additions"] == 1
    assert res["stats"]["deletions"] == 1
    assert res["stats"]["unchanged"] == 2
    assert res["stats"]["total_changes"] == 2


def test_diff_identical_text_no_changes():
    res = compute_prompt_diff("same\nthing", "same\nthing")
    assert res["stats"]["additions"] == 0
    assert res["stats"]["deletions"] == 0