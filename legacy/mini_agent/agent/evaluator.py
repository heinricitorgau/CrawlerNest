from __future__ import annotations


def evaluate_output(output: str) -> dict[str, object]:
    score = 0.3
    lowered = output.lower()
    feedback: list[str] = []

    if len(output) > 80:
        score += 0.2
    else:
        feedback.append("Output is too short.")

    if "def " in output or "class " in output:
        score += 0.2
    else:
        feedback.append("Add clearer implementation structure.")

    if "tool result" in lowered or "memory" in lowered:
        score += 0.1
    else:
        feedback.append("Use tool or memory context more explicitly.")

    if "return" in lowered:
        score += 0.1
    else:
        feedback.append("Include a concrete return path.")

    if "parser" in lowered or "extractor" in lowered:
        score += 0.1

    final_score = min(score, 0.9)
    return {"score": round(final_score, 2), "feedback": feedback}

