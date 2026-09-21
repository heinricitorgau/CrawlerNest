"""Turning a response body into text, using the charset the server declared.

Three fetch paths in this repo used to answer "what encoding is this?" three
different ways, none of which read the declaration:

- ``crawlernest-crawler-core/http_client.py`` hard-coded ``decode("utf-8",
  errors="replace")``. A Windows-1252 response lost every accented character to
  U+FFFD, and a genuine en dash (byte 0x96) with it.
- ``crawlernest-extractors/transport.py`` never set ``.encoding``, so the
  ``requests`` fallback path inherited requests' RFC-2616 behaviour: ``text/html``
  with no charset parameter decodes as **ISO-8859-1**. That maps 0x80-0x9F to C1
  control characters and every other high byte to the wrong letter, silently.
- the same code on the curl_cffi backend defaults to UTF-8 instead, so the two
  backends disagreed about the same bytes -- which is how
  ``University of Tennessee, Knoxville \\x96 Haslam College of Business`` reached
  ``analytics.missing_entity_log`` with a control character where a dash belongs.

So the rule lives here once, and the answer says where it came from.

The fallback is **cp1252, never latin-1**. The two agree on 0xA0-0xFF and differ
exactly where it matters: latin-1 maps 0x80-0x9F to unprintable C1 controls,
while cp1252 maps them to the punctuation those bytes mean in practice -- 0x96 is
an en dash, 0x92 a right single quote. A name is text a person wrote, so the
reading that yields punctuation is the one worth guessing. An explicitly declared
latin-1 is still honoured: that is the server's statement about its own bytes,
and inventing one is the defect, not believing one.

This module sits in ``crawlernest-core`` because ``bootstrap_module_paths`` puts
that directory on ``sys.path`` for every pipeline command, which is the only
directory both the extractor and the crawler-core fetch paths can reach.
"""

from __future__ import annotations

import codecs
import re
from dataclasses import dataclass
from typing import Optional

__all__ = [
    "DecodedText",
    "FALLBACK_ENCODING",
    "charset_from_bom",
    "charset_from_content_type",
    "charset_from_html_meta",
    "decode_http_text",
]

#: See the module docstring: cp1252 over latin-1, deliberately.
FALLBACK_ENCODING = "cp1252"

#: How far into the body an HTML charset declaration is looked for. The HTML
#: standard requires it inside the first 1024 bytes; a little slack costs
#: nothing and catches pages with a long comment before <head>.
META_SCAN_BYTES = 2048

_CHARSET_IN_CONTENT_TYPE = re.compile(r"charset\s*=\s*\"?([\w:.+-]+)\"?", re.IGNORECASE)
_META_CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([\w:.+-]+)""", re.IGNORECASE)

_BOMS: tuple[tuple[bytes, str], ...] = (
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)


@dataclass(frozen=True, slots=True)
class DecodedText:
    """The decoded body, and how the encoding was decided.

    ``source`` and ``replacements`` exist so a caller can record the decision
    rather than discover it later from a mangled name: a crawl that fell through
    to the fallback, or replaced characters, is a crawl worth a line in
    ``crawl_meta.json``.
    """

    text: str
    encoding: str
    source: str
    replacements: int = 0

    @property
    def is_declared(self) -> bool:
        """Did the response say what it was, rather than us guessing?"""
        return self.source in {"bom", "header", "meta"}


def charset_from_content_type(content_type: Optional[str]) -> Optional[str]:
    """The charset parameter, when the header carries one Python can use."""
    if not content_type:
        return None
    found = _CHARSET_IN_CONTENT_TYPE.search(content_type)
    if not found:
        return None
    return _known_codec(found.group(1))


def charset_from_bom(body: bytes) -> Optional[str]:
    """The encoding a byte-order mark states outright."""
    for bom, encoding in _BOMS:
        if body.startswith(bom):
            return encoding
    return None


def charset_from_html_meta(body: bytes) -> Optional[str]:
    """The charset an HTML document declares in its own head."""
    found = _META_CHARSET.search(body[:META_SCAN_BYTES])
    if not found:
        return None
    try:
        declared = found.group(1).decode("ascii")
    except UnicodeDecodeError:
        return None
    return _known_codec(declared)


def decode_http_text(
    body: bytes,
    content_type: Optional[str] = None,
    *,
    fallback: str = FALLBACK_ENCODING,
) -> DecodedText:
    """Decode a response body, preferring what the response says about itself.

    Order: byte-order mark, then the ``Content-Type`` charset, then an HTML
    ``<meta charset>``, then strict UTF-8, then ``fallback``. JSON is the one
    exception -- RFC 8259 fixes it to UTF-8 and a charset parameter on it is
    non-standard, so UTF-8 is tried before a declaration that would contradict
    the format.

    Nothing is dropped quietly: when even the fallback needs replacements, the
    count comes back with the text.
    """
    if not isinstance(body, (bytes, bytearray)):
        raise TypeError(f"body must be bytes, not {type(body).__name__}")
    body = bytes(body)
    if not body:
        return DecodedText(text="", encoding="utf-8", source="empty")

    bom = charset_from_bom(body)
    if bom:
        strict = _try_strict(body, bom)
        if strict is not None:
            return DecodedText(text=strict, encoding=bom, source="bom")

    declared = charset_from_content_type(content_type)
    if declared and _needs_a_bom(declared):
        # No BOM reached us -- see above, it is checked first -- so the byte
        # order is unstated. utf-16 will decode two arbitrary bytes into some
        # character rather than raise, so honouring this label would turn a
        # valid document into plausible-looking nonsense instead of an error.
        declared = None
    json_like = _is_json(content_type)

    # RFC 8259: JSON is UTF-8. Trying it first means a stray "charset=iso-8859-1"
    # on a JSON endpoint cannot turn a valid document into mojibake.
    if json_like:
        strict = _try_strict(body, "utf-8")
        if strict is not None:
            return DecodedText(text=strict, encoding="utf-8", source="json-utf-8")

    if declared:
        strict = _try_strict(body, declared)
        if strict is not None:
            return DecodedText(text=strict, encoding=declared, source="header")
        # A declaration the bytes contradict is worth keeping rather than
        # trusting: fall through to sniffing and report which one won.

    meta = charset_from_html_meta(body) if _is_html(content_type, body) else None
    if meta:
        strict = _try_strict(body, meta)
        if strict is not None:
            return DecodedText(text=strict, encoding=meta, source="meta")

    strict = _try_strict(body, "utf-8")
    if strict is not None:
        return DecodedText(text=strict, encoding="utf-8", source="utf-8")

    text = body.decode(fallback, errors="replace")
    return DecodedText(
        text=text,
        encoding=fallback,
        source="fallback",
        replacements=text.count("�"),
    )


# -- internals ---------------------------------------------------------------


def _known_codec(name: str) -> Optional[str]:
    candidate = name.strip().strip("\"'").lower()
    if not candidate:
        return None
    try:
        codecs.lookup(candidate)
    except LookupError:
        return None
    return candidate


def _needs_a_bom(encoding: str) -> bool:
    """Is this a codec whose successful decode proves nothing?

    utf-16 and utf-32 map almost any body of the right length to *some* string,
    so a strict decode cannot tell a correct label from a wrong one. In HTTP they
    are carried with a byte-order mark; without one the declaration is not usable
    evidence.
    """
    normalised = encoding.replace("_", "-").lower()
    return normalised.startswith(("utf-16", "utf-32")) and not normalised.endswith(("-le", "-be"))


def _try_strict(body: bytes, encoding: str) -> Optional[str]:
    """The decoded text, or None when these bytes are not that encoding.

    Strict on purpose. A decode that needs ``errors="replace"`` has not read the
    body, it has guessed at it, and the caller deserves to know the difference.
    """
    try:
        return body.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        return None


def _mime_of(content_type: Optional[str]) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


def _is_json(content_type: Optional[str]) -> bool:
    mime = _mime_of(content_type)
    return mime == "application/json" or mime.endswith("+json")


def _is_html(content_type: Optional[str], body: bytes) -> bool:
    mime = _mime_of(content_type)
    if mime in {"text/html", "application/xhtml+xml"}:
        return True
    if mime:
        return False
    # No content type at all: the body can still say what it is.
    return body[:META_SCAN_BYTES].lstrip()[:15].lower().startswith((b"<!doctype", b"<html"))
