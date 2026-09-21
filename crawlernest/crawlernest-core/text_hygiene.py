"""The characters a university name must not reach the warehouse carrying.

Two kinds got in, and both cost something measurable:

- ``City St George's,\\xa0University of\\xa0London`` -- THE's 2026 table uses
  no-break spaces inside the name. It renders identically to a normal space and
  compares unequal to one, so the resolver missed the canonical record that
  differs from it by nothing else, and the name went to
  ``analytics.missing_entity_log`` nine times before a later normaliser happened
  to collapse it.
- ``University of Tennessee, Knoxville \\x96 Haslam College of Business`` -- byte
  0x96 is an en dash in Windows-1252 and an unprintable C1 control in
  ISO-8859-1, and a fetch path that guessed the latter put the control character
  in the name. ``http_text`` stops new ones arriving; this is the door they
  would have been caught at either way.

So the rule is: a control character is never part of a name, and a space is a
space. Both are applied, and what was applied is recorded -- a silent cleanup
would leave the next reader unable to tell a crawler bug from a school that
really is called that.

Deliberately not applied to source entity ids or URLs. An id is a key: two
copies of it have to compare equal across runs, and "improving" one silently
re-keys a mapping. Only text a person wrote and a person reads goes through
here.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

__all__ = ["CleanedText", "clean_source_text", "has_control_characters"]

#: Spaces that are not U+0020 but mean one. Mapped rather than stripped: the
#: name is the same name, and a reader comparing it to a canonical record should
#: not have to know which space the source used.
_SPACE_LIKE = {
    " ": "no-break space",
    " ": "ogham space",
    " ": "en quad",
    " ": "em quad",
    " ": "en space",
    " ": "em space",
    " ": "three-per-em space",
    " ": "four-per-em space",
    " ": "six-per-em space",
    " ": "figure space",
    " ": "punctuation space",
    " ": "thin space",
    " ": "hair space",
    " ": "narrow no-break space",
    " ": "medium mathematical space",
    "　": "ideographic space",
}

#: Zero-width characters: invisible, and they break equality just as quietly.
_ZERO_WIDTH = {
    "​": "zero-width space",
    "‌": "zero-width non-joiner",
    "‍": "zero-width joiner",
    "⁠": "word joiner",
    "﻿": "byte-order mark",
}

#: C1 controls carry the payload of a Windows-1252 byte read as ISO-8859-1.
#: Re-reading them through cp1252 recovers the punctuation the source meant;
#: the five bytes cp1252 leaves undefined have nothing to recover and go.
_C1_RANGE = range(0x80, 0xA0)

_WHITESPACE_RUN = re.compile(r" {2,}")


@dataclass(frozen=True, slots=True)
class CleanedText:
    """The text to store, and what had to be done to it.

    ``changes`` is empty for the overwhelming majority of names. When it is not,
    it is worth putting in the row's metadata: it says a source sent something a
    name cannot contain, which is a fact about the crawl and not about the
    university.
    """

    text: str
    changes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def was_changed(self) -> bool:
        return bool(self.changes)


def has_control_characters(value: str) -> bool:
    """Any C0 or C1 control character, which no name legitimately contains."""
    return any(unicodedata.category(ch) == "Cc" for ch in value)


def clean_source_text(value: Optional[str]) -> CleanedText:
    """Normalise a name a source printed, reporting what was wrong with it.

    Order matters: the C1 controls are recovered before whitespace is collapsed,
    because one of them (0x96, an en dash) is a visible character that belongs in
    the name and must not be mistaken for padding.
    """
    if value is None:
        return CleanedText(text="")

    text = str(value)
    changes: list[str] = []

    if any(ord(ch) in _C1_RANGE for ch in text):
        text, recovered = _recover_c1(text)
        changes.extend(recovered)

    for char, label in _ZERO_WIDTH.items():
        if char in text:
            text = text.replace(char, "")
            changes.append(f"removed {label}")

    for char, label in _SPACE_LIKE.items():
        if char in text:
            text = text.replace(char, " ")
            changes.append(f"replaced {label} with a space")

    # Tabs and newlines inside a name are formatting that leaked out of a table.
    leaked = {ch for ch in text if unicodedata.category(ch) == "Cc"}
    if leaked:
        for ch in leaked:
            text = text.replace(ch, " ")
        changes.append("replaced control characters with spaces")

    collapsed = _WHITESPACE_RUN.sub(" ", text).strip()
    if collapsed != text:
        text = collapsed
        # Not reported on its own: trimming is ordinary, and _to_optional_str
        # already stripped. It is only ever a consequence of the above.

    return CleanedText(text=text, changes=tuple(changes))


def _recover_c1(text: str) -> tuple[str, list[str]]:
    """Read C1 controls back through cp1252, which is where they came from."""
    out: list[str] = []
    changes: list[str] = []
    for ch in text:
        if ord(ch) not in _C1_RANGE:
            out.append(ch)
            continue
        try:
            recovered = bytes([ord(ch)]).decode("cp1252")
        except UnicodeDecodeError:
            # 0x81, 0x8d, 0x8f, 0x90 and 0x9d are undefined in cp1252: there is
            # no character to recover, so the name is better without it.
            changes.append(f"dropped undefined control U+{ord(ch):04X}")
            continue
        out.append(recovered)
        changes.append(f"read U+{ord(ch):04X} as cp1252 {recovered!r}")
    return "".join(out), changes
