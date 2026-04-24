from crawlernest_admission_crawler.resolver import (
    ResolvedAdmissionField,
    resolve_admission_field,
    resolve_admission_signals,
)
from crawlernest_admission_crawler.signals import AdmissionSignal


def signal(
    field,
    value,
    *,
    confidence=0.8,
    source_type="official_admission_page",
    extraction_method="rule_based",
    status="accepted",
    source_url=None,
    evidence_text="evidence",
    notes=None,
):
    return AdmissionSignal(
        field=field,
        value=value,
        source_url=source_url,
        source_type=source_type,
        confidence=confidence,
        extraction_method=extraction_method,
        evidence_text=evidence_text,
        status=status,
        notes=notes,
    )


def test_single_signal():
    resolved = resolve_admission_signals(
        [signal("ielts", 6.5, source_url="https://example.edu/admissions")]
    )

    result = resolved["ielts"]
    assert isinstance(result, ResolvedAdmissionField)
    assert result.resolved_value == 6.5
    assert result.confidence == 0.8
    assert result.source_count == 1
    assert result.sources == ["https://example.edu/admissions"]
    assert result.status == "accepted"


def test_multiple_same_values():
    resolved = resolve_admission_signals(
        [
            signal("ielts", 6.5, confidence=0.8, source_url="https://a.example"),
            signal("ielts", 6.5, confidence=0.7, source_url="https://b.example"),
        ]
    )

    result = resolved["ielts"]
    assert result.resolved_value == 6.5
    assert result.confidence == 0.85
    assert result.source_count == 2
    assert result.status == "accepted"
    assert result.resolution_reason == "all usable signals agree"


def test_numeric_conflict_ielts_uses_highest_requirement():
    resolved = resolve_admission_signals(
        [
            signal("ielts", 6.5, confidence=0.85),
            signal("ielts", 7.0, confidence=0.7),
        ]
    )

    result = resolved["ielts"]
    assert result.resolved_value == 7.0
    assert result.status == "accepted"
    assert result.resolution_reason == "multiple values found, using highest requirement"


def test_deadline_merge():
    resolved = resolve_admission_signals(
        [
            signal("deadline", "2025-12-01", notes="deadline_type=early"),
            signal("deadline", "2026-04-15", notes="deadline_type=final"),
            signal("deadline", "2026-02-01", notes="deadline_type=rolling"),
        ]
    )

    result = resolved["deadline"]
    assert result.resolved_value == {
        "early": "2025-12-01",
        "final": "2026-04-15",
        "rolling": "2026-02-01",
    }
    assert result.status == "accepted"


def test_rejected_filtered():
    resolved = resolve_admission_signals(
        [
            signal("ielts", 9.0, confidence=0.95, status="rejected"),
            signal("ielts", 6.5, confidence=0.75),
        ]
    )

    result = resolved["ielts"]
    assert result.resolved_value == 6.5
    assert result.confidence == 0.75
    assert result.source_count == 1
    assert result.status == "accepted"


def test_confidence_aggregation():
    resolved = resolve_admission_signals(
        [
            signal("gpa", 3.0, confidence=0.7),
            signal("gpa", 3.0, confidence=0.6),
            signal("gpa", 3.0, confidence=0.5),
            signal("gpa", 3.0, confidence=0.4),
            signal("gpa", 3.0, confidence=0.3),
        ]
    )

    assert resolved["gpa"].confidence == 0.85


def test_all_needs_review():
    resolved = resolve_admission_signals(
        [
            signal("ielts", 10.0, confidence=0.4, status="needs_review"),
            signal("ielts", 11.0, confidence=0.3, status="needs_review"),
        ]
    )

    result = resolved["ielts"]
    assert result.resolved_value == 11.0
    assert result.status == "needs_review"


def test_empty_input():
    assert resolve_admission_signals([]) == {}

    missing = resolve_admission_field("ielts", [])
    assert missing.resolved_value is None
    assert missing.confidence == 0.0
    assert missing.source_count == 0
    assert missing.status == "missing"


def test_mixed_confidence_ordering():
    resolved = resolve_admission_signals(
        [
            signal(
                "country",
                "Canada",
                confidence=0.6,
                source_type="official_admission_page",
            ),
            signal(
                "country",
                "Australia",
                confidence=0.9,
                source_type="aggregator",
            ),
        ]
    )

    result = resolved["country"]
    assert result.resolved_value == "Australia"
    assert result.status == "conflict"
    assert result.resolution_reason == "conflicting non-numeric values found, using best-ranked signal"


def test_source_priority_override():
    resolved = resolve_admission_signals(
        [
            signal(
                "country",
                "Australia",
                confidence=0.8,
                source_type="aggregator",
            ),
            signal(
                "country",
                "Canada",
                confidence=0.8,
                source_type="official_admission_page",
            ),
        ]
    )

    result = resolved["country"]
    assert result.resolved_value == "Canada"
    assert result.status == "conflict"
