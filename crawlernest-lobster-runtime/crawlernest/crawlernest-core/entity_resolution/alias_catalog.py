from __future__ import annotations

from .normalizer import normalize_university_name


HIGH_CONFIDENCE_ALIAS_GROUPS: tuple[tuple[str, ...], ...] = (
    (
        "Ludwig-Maximilians-Universität München",
        "Ludwig-Maximilians-Universitat Munchen",
        "Ludwig Maximilian University of Munich",
        "LMU Munich",
    ),
    (
        "University of California, Berkeley",
        "University of California Berkeley",
        "UC Berkeley",
        "UCB",
    ),
    (
        "The University of Hong Kong",
        "University of Hong Kong",
        "HKU",
    ),
    (
        "National University of Singapore",
        "NUS",
    ),
    (
        "EPFL – École polytechnique fédérale de Lausanne",
        "EPFL - Ecole polytechnique federale de Lausanne",
        "École polytechnique fédérale de Lausanne",
        "Ecole polytechnique federale de Lausanne",
        "EPFL",
    ),
)


def curated_alias_variants(display_name: str, aliases: tuple[str, ...] = ()) -> tuple[str, ...]:
    known_keys = {
        normalize_university_name(display_name),
        *(normalize_university_name(alias) for alias in aliases),
    }
    out: set[str] = set()
    for group in HIGH_CONFIDENCE_ALIAS_GROUPS:
        group_keys = {normalize_university_name(value) for value in group}
        if known_keys.intersection(group_keys):
            out.update(value.strip() for value in group if str(value or "").strip())
    return tuple(sorted(out))
