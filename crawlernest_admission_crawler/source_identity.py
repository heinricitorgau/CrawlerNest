"""The stable identity an admission row is reviewed under.

warehouse.mapping_review reviews a ``(source_code, source_entity_id)`` pair.
Ranking rows have always carried an id from the source; admission rows have
not. Their natural key is ``(normalized_university_name, source_url)``, and
``normalized_university_name`` is the very value entity resolution decides --
so a decision keyed on it silently stops applying the day the name normalizes
differently.

The identity is therefore derived from the URL alone and deliberately contains
no university name.

This is mirrored by the backfill in
``crawlernest/crawlernest-schema/admission_postgresql.sql``. If one changes,
both change.
"""

from __future__ import annotations

import re

SOURCE_CODE = "university_site"

_SCHEME_RE = re.compile(r"^https?://", re.IGNORECASE)
_QUERY_OR_FRAGMENT_RE = re.compile(r"[?#].*$", re.DOTALL)


def admission_source_entity_id(source_url: str) -> str:
    """Reduce *source_url* to the identity a review decision hangs on.

    Lowercased, scheme removed, query and fragment dropped, trailing slashes
    stripped::

        >>> admission_source_entity_id(
        ...     "https://www.ucl.ac.uk/prospective-students/graduate/english-language/"
        ... )
        'www.ucl.ac.uk/prospective-students/graduate/english-language'

    Not truncated. ``_url_to_slug`` in the crawler caps its output at 80
    characters because it is naming a file; two long URLs sharing a prefix
    would collide, and a collision here would merge two universities' review
    decisions.
    """
    text = _SCHEME_RE.sub("", str(source_url or "").strip().lower())
    text = _QUERY_OR_FRAGMENT_RE.sub("", text)
    return text.rstrip("/")
