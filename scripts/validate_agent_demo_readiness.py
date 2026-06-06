#!/usr/bin/env python3
"""Validate Agent demo readiness artifacts.

Readonly validation only: checks files and expected boundary wording. It does
not call providers, run tools, write databases, or mutate runtime state.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DOCS = [
    "docs/AGENT_DEMO_PROMPTS.md",
    "docs/AGENT_DEMO_EVALUATION.md",
    "docs/AGENT_PROVIDER_MATRIX.md",
    "docs/AGENT_DEMO_FALLBACK.md",
    "docs/AGENT_MODEL_INTEGRATION.md",
]

REQUIRED_FILES = [
    "crawlernest/crawlernest-web/src/lib/agentResponseRubric.ts",
    "crawlernest/crawlernest-web/src/lib/agentSystemPrompt.ts",
]

READONLY_TERMS = [
    "readonly",
    "advisory-only",
    "no tool calling",
    "no DB writes",
    "no shell execution",
    "no repo mutation",
    "no pipeline execution",
    "no autonomous behavior",
]

DOC_EXPECTATIONS = {
    "docs/AGENT_DEMO_PROMPTS.md": [
        "Why does source disagreement matter?",
        "What does stale data mean?",
        "How should I interpret recommendation confidence?",
        "Why is explainability important?",
        "Why is THE unavailable?",
    ],
    "docs/AGENT_DEMO_EVALUATION.md": [
        "Good Answer Should",
        "Bad Answer Examples",
        "I fixed the data",
        "I reran the rankings",
        "I updated the database",
    ],
    "docs/AGENT_PROVIDER_MATRIX.md": [
        "mock",
        "ollama",
        "openai",
        "Competition default",
        "mock",
        "ollama",
    ],
    "docs/AGENT_DEMO_FALLBACK.md": [
        "Ollama unavailable",
        "OpenAI unavailable",
        "timeout",
        "API key missing",
        "provider misconfigured",
    ],
}


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    failures: list[str] = []

    for path in [*REQUIRED_DOCS, *REQUIRED_FILES]:
        require((ROOT / path).is_file(), f"missing required file: {path}", failures)

    for path, expected_terms in DOC_EXPECTATIONS.items():
        if not (ROOT / path).is_file():
            continue
        content = read(path)
        for term in expected_terms:
            require(term in content, f"{path} missing expected term: {term}", failures)

    combined = "\n".join(read(path) for path in REQUIRED_DOCS if (ROOT / path).is_file())
    for term in READONLY_TERMS:
        require(term in combined, f"readonly wording missing: {term}", failures)

    rubric = read("crawlernest/crawlernest-web/src/lib/agentResponseRubric.ts")
    for term in [
        "accurate",
        "caveat-aware",
        "concise",
        "advisory-only",
        "authority inflation",
        "hidden limitations",
        "fake certainty",
        "system mutation claims",
    ]:
        require(term in rubric, f"rubric missing: {term}", failures)

    if failures:
        print("[agent-demo-readiness] FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("[agent-demo-readiness] PASS")
    print(f"docs_checked={len(REQUIRED_DOCS)}")
    print("readonly_boundary=present")
    print("provider_matrix=present")
    print("fallback_doc=present")
    print("rubric=present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
