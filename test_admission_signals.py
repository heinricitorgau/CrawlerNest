from crawlernest_admission_crawler.signals import (
    AdmissionSignal,
    build_admission_signal,
    calculate_default_confidence,
    validate_admission_signal,
)


def test_valid_ielts_signal():
    signal = build_admission_signal(
        field="ielts",
        value=6.5,
        source_type="official_admission_page",
        extraction_method="rule_based",
        evidence_text="IELTS overall score of at least 6.5",
        source_url="https://example.edu/admissions",
    )

    assert signal.status == "accepted"
    assert validate_admission_signal(signal) == []


def test_invalid_ielts_signal_becomes_needs_review():
    signal = build_admission_signal(
        field="ielts",
        value=10.0,
        source_type="official_admission_page",
        extraction_method="rule_based",
        evidence_text="IELTS overall score of at least 10.0",
    )

    assert signal.status == "needs_review"
    assert "invalid_ielts_value" in validate_admission_signal(signal)


def test_official_rule_based_confidence_is_085():
    signal = build_admission_signal(
        field="ielts",
        value=6.5,
        source_type="official_admission_page",
        extraction_method="rule_based",
        evidence_text="IELTS overall score of at least 6.5",
    )

    assert signal.confidence == 0.85


def test_missing_evidence_lowers_confidence():
    signal = build_admission_signal(
        field="ielts",
        value=6.5,
        source_type="official_admission_page",
        extraction_method="rule_based",
        evidence_text=None,
    )

    assert signal.confidence == 0.75


def test_anomaly_lowers_confidence():
    signal = build_admission_signal(
        field="ielts",
        value=6.5,
        source_type="official_admission_page",
        extraction_method="rule_based",
        evidence_text="IELTS overall score of at least 6.5",
        anomaly=True,
    )

    assert signal.confidence == 0.65


def test_deadline_iso_validation():
    valid_signal = build_admission_signal(
        field="deadline",
        value="2026-04-15",
        source_type="official_admission_page",
        extraction_method="rule_based",
        evidence_text="Final deadline is 2026-04-15.",
    )
    invalid_signal = build_admission_signal(
        field="deadline",
        value="04/15/2026",
        source_type="official_admission_page",
        extraction_method="rule_based",
        evidence_text="Final deadline is 04/15/2026.",
    )

    assert validate_admission_signal(valid_signal) == []
    assert invalid_signal.status == "needs_review"
    assert "invalid_deadline_value" in validate_admission_signal(invalid_signal)


def test_invalid_field_rejected():
    signal = AdmissionSignal(
        field="sat",
        value=1400,
        source_url=None,
        source_type="official_admission_page",
        confidence=0.85,
        extraction_method="rule_based",
        evidence_text="SAT score of 1400.",
        status="accepted",
        notes=None,
    )

    errors = validate_admission_signal(signal)

    assert signal.status == "needs_review"
    assert "invalid_field:sat" in errors


def test_confidence_clamp_works():
    assert calculate_default_confidence(
        source_type="unknown",
        extraction_method="unknown",
        evidence_text=None,
        anomaly=True,
    ) == 0.10
    assert build_admission_signal(
        field="ielts",
        value=6.5,
        confidence=2.0,
        evidence_text="IELTS overall score of at least 6.5",
    ).confidence == 1.0
    assert build_admission_signal(
        field="ielts",
        value=6.5,
        confidence=-1.0,
        evidence_text="IELTS overall score of at least 6.5",
    ).confidence == 0.0
