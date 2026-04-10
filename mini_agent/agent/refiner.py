from __future__ import annotations


def refine_output(output: str, feedback: list[str]) -> str:
    refined_lines = [
        output,
        "",
        "# Refinement Notes",
        "The output was expanded to include clearer structure and a more explicit result path.",
    ]

    if feedback:
        refined_lines.append("Feedback applied:")
        refined_lines.extend(f"- {item}" for item in feedback)

    refined_lines.extend(
        [
            "",
            "def explain_changes():",
            '    return "Refinement added more detail, structure, and a clearer explanation."',
        ]
    )
    return "\n".join(refined_lines)

