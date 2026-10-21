"""Whether a name can be given to a university as an alias without taking another university's rows.

The resolver tries aliases before display names, and an exact alias match ignores the
country. So an alias that is also how a second university is known does not produce an
ambiguity the resolver would notice: it silently wins. "Northeastern University
(Shenyang)" is indexed as "Northeastern University" too -- the one in Boston. Anything that
writes ``warehouse.university_alias`` in bulk asks here first.
"""
from __future__ import annotations

import re
from typing import Mapping, Optional

from .normalizer import expanded_transliteration, normalize_university_name

__all__ = ["alias_is_safe", "has_disambiguator", "resolver_keys"]


def _strip_parenthetical_suffix(name: str) -> str:
    # The same expression as EntityResolver._strip_parenthetical_suffix.
    return re.sub(r"\s*\([^)]*\)\s*$", "", str(name or "")).strip()


def has_disambiguator(name: str) -> bool:
    """True for "University of New England (Australia)": the parenthesis is there because the bare name is shared.

    The resolver indexes the bare name as well, and the university it is shared with may not
    be in the warehouse yet for :func:`alias_is_safe` to see.
    """
    return _strip_parenthetical_suffix(name) != str(name or "").strip()


def resolver_keys(name: str) -> set[str]:
    """Every key the resolver indexes ``name`` under: raw, normalised and transliterated, with and without a trailing parenthesis."""
    keys: set[str] = set()
    for variant in {str(name or "").strip(), _strip_parenthetical_suffix(name)}:
        if not variant:
            continue
        keys.add("raw:" + variant.lower())
        for key in (normalize_university_name(variant), expanded_transliteration(variant)):
            if key:
                keys.add("norm:" + key)
    return keys


def alias_is_safe(alias: str, canonical_university_id: int, names_by_canonical: Mapping[int, set[str]]) -> Optional[str]:
    """None if no other university is reachable by this alias; otherwise which one is.

    ``names_by_canonical`` maps every active university to the union of
    :func:`resolver_keys` over its display name and aliases.
    """
    keys = resolver_keys(alias)
    for other_id, held in names_by_canonical.items():
        if other_id != canonical_university_id and keys & held:
            return f"also a name of canonical {other_id}"
    return None
