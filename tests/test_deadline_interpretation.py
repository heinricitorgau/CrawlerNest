from crawlernest_admission_crawler.deadline_interpretation import interpret_deadline_decision


def test_early_vs_final_priority():
    result = interpret_deadline_decision(
        deadline="2025-12-01",
        diagnostics={
            "deadline_candidates": [("early", "2025-12-01"), ("final", "2026-04-15")],
            "deadline_conflict": True,
        },
    )
    assert result["recommended_deadline"] == "2025-12-01", result
    assert result["recommended_deadline_type"] == "early", result
    assert result["deadline_urgency"] == "high", result


def test_international_vs_domestic_priority():
    result = interpret_deadline_decision(
        deadline="2026-04-15",
        diagnostics={
            "deadline_candidates": [("international", "2026-04-15"), ("domestic", "2026-06-30")],
            "deadline_conflict": True,
        },
    )
    assert result["recommended_deadline"] == "2026-04-15", result
    assert result["recommended_deadline_type"] == "international", result
    assert result["deadline_urgency"] == "high", result


def test_single_rolling_deadline():
    result = interpret_deadline_decision(
        deadline="2026-06-30",
        diagnostics={"deadline_candidates": [("rolling", "2026-06-30")]},
    )
    assert result["recommended_deadline"] == "2026-06-30", result
    assert result["recommended_deadline_type"] == "rolling", result
    assert result["deadline_urgency"] == "low", result


def test_no_deadline_candidates():
    result = interpret_deadline_decision(deadline=None, diagnostics={})
    assert result["recommended_deadline"] is None, result
    assert result["recommended_deadline_type"] == "unknown", result
    assert result["deadline_urgency"] == "unknown", result


if __name__ == "__main__":
    tests = [
        test_early_vs_final_priority,
        test_international_vs_domestic_priority,
        test_single_rolling_deadline,
        test_no_deadline_candidates,
    ]
    for test in tests:
        try:
            test()
            print(f"{test.__name__}: PASS")
        except AssertionError as exc:
            print(f"{test.__name__}: FAIL\n{exc}")
