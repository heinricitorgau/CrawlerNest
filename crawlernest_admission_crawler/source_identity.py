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


def admission_entity_host(source_entity_id: str | None) -> str | None:
    """The host an admission entity id lives on: what names the institution.

    ``multi_source.reviews`` recognises a reviewed entity that came back under a
    new id by the id's last segment. For admission ids that segment is a page
    name -- ``english-language-requirements`` ends the UCL, Melbourne and Toronto
    ids alike -- so it would match unrelated universities and refuse every run.
    A university moving its requirements page keeps its host far more often
    than its path, and two universities do not share one.
    """
    text = str(source_entity_id or "").strip().lower()
    host = text.split("/", 1)[0]
    return host or None


_KEY_SPACE_RE = re.compile(r"\s+")


def _key_part(value: str | None) -> str:
    return _KEY_SPACE_RE.sub(" ", str(value or "").strip().lower())


def admission_programme_key(faculty: str | None, programme_name: str | None) -> str:
    """The programme half of an admission row's natural key.

    ``faculty|programme``, lowercased with whitespace collapsed, so the same
    programme printed as "MSc  Computing" and "MSc Computing" is one row. Empty
    when neither is named: an institution-wide or unspecified requirement.
    Mirrored by ck_admission_record_programme_names, which requires exactly that
    emptiness, in crawlernest-schema/admission_postgresql.sql.
    """
    faculty_part, programme_part = _key_part(faculty), _key_part(programme_name)
    if not faculty_part and not programme_part:
        return ""
    return f"{faculty_part}|{programme_part}"
