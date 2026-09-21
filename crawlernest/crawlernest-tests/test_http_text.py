"""The decode rule, and the two defects it was written to close.

Both are recorded here as bytes rather than as descriptions, because both
reached the warehouse and neither raised anything:

- ``University of Tennessee, Knoxville \\x96 Haslam College of Business`` sat in
  analytics.missing_entity_log with U+0096, a C1 control, where an en dash
  belongs. Byte 0x96 is an en dash in Windows-1252 and a control character in
  ISO-8859-1, and ``requests`` invents ISO-8859-1 for ``text/html`` that declares
  no charset -- so the name was mangled by a default nobody chose.
- the same page fetched through curl_cffi came back as UTF-8 instead, so the two
  backends produced different names from identical bytes.

The point of ``decode_http_text`` is that neither the library nor the backend
decides any more. A local HTTP server serves the real byte sequences, so these
tests exercise the same path a crawl takes, offline.
"""

from __future__ import annotations

import http.server
import socket
import threading
import unittest
from pathlib import Path
import sys

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-core"))

from http_text import (  # noqa: E402
    DecodedText,
    charset_from_bom,
    charset_from_content_type,
    charset_from_html_meta,
    decode_http_text,
)

#: The Tennessee row, as the bytes a Windows-1252 server sends.
CP1252_DASH = b"University of Tennessee, Knoxville \x96 Haslam College of Business"
#: The same sentence a UTF-8 server sends.
UTF8_DASH = "University of Tennessee, Knoxville – Haslam College of Business".encode("utf-8")
#: An accented name, in each of the two encodings.
CP1252_NAME = b"Universidad Nacional de Tucum\xe1n"
UTF8_NAME = "Universidad Nacional de Tucumán".encode("utf-8")


class TestTheDeclarationIsBelieved(unittest.TestCase):
    def test_a_declared_charset_is_used(self) -> None:
        decoded = decode_http_text(CP1252_DASH, "text/html; charset=windows-1252")
        self.assertIn("–", decoded.text)
        self.assertEqual("windows-1252", decoded.encoding)
        self.assertEqual("header", decoded.source)
        self.assertTrue(decoded.is_declared)

    def test_a_declared_latin_1_is_still_believed(self) -> None:
        # Honouring a declaration is not the bug; inventing one is. A server that
        # says latin-1 is describing its own bytes, and 0x96 there really is a
        # control character.
        decoded = decode_http_text(CP1252_DASH, "text/html; charset=iso-8859-1")
        self.assertIn("", decoded.text)
        self.assertEqual("iso-8859-1", decoded.encoding)

    def test_a_byte_order_mark_outranks_the_header(self) -> None:
        body = "﻿Universidad Nacional de Tucumán".encode("utf-8")
        decoded = decode_http_text(body, "text/html; charset=windows-1252")
        self.assertEqual("Universidad Nacional de Tucumán", decoded.text)
        self.assertEqual("bom", decoded.source)

    def test_an_html_meta_charset_is_read_when_the_header_is_silent(self) -> None:
        body = b"<html><head><meta charset='windows-1252'></head><body>" + CP1252_NAME + b"</body></html>"
        decoded = decode_http_text(body, "text/html")
        self.assertIn("Tucumán", decoded.text)
        self.assertEqual("meta", decoded.source)

    def test_a_declaration_the_bytes_contradict_does_not_win(self) -> None:
        # utf-8 bytes under a utf-16 label: believing it would raise or produce
        # nonsense, so the sniff takes over and says so.
        decoded = decode_http_text(UTF8_NAME, "text/html; charset=utf-16")
        self.assertEqual("Universidad Nacional de Tucumán", decoded.text)
        self.assertEqual("utf-8", decoded.source)


class TestNothingDefaultsToLatin1(unittest.TestCase):
    """The defect: a silent ISO-8859-1 default for undeclared text/html."""

    def test_undeclared_utf8_html_is_read_as_utf8(self) -> None:
        decoded = decode_http_text(b"<html><body>" + UTF8_NAME + b"</body></html>", "text/html")
        self.assertIn("Tucumán", decoded.text)
        self.assertEqual("utf-8", decoded.encoding)

    def test_undeclared_cp1252_html_keeps_the_punctuation(self) -> None:
        # The Tennessee case. latin-1 would give U+0096; cp1252 gives the dash
        # the source meant, and the result records that it was a guess.
        decoded = decode_http_text(b"<html><body>" + CP1252_DASH + b"</body></html>", "text/html")
        self.assertIn("–", decoded.text)
        self.assertNotIn("", decoded.text)
        self.assertEqual("cp1252", decoded.encoding)
        self.assertEqual("fallback", decoded.source)
        self.assertFalse(decoded.is_declared)

    def test_no_c1_control_ever_survives_an_undeclared_body(self) -> None:
        for byte, expected in ((b"\x96", "–"), (b"\x92", "’"), (b"\x93", "“")):
            with self.subTest(byte=byte):
                decoded = decode_http_text(b"Name " + byte + b" more", "text/html")
                self.assertIn(expected, decoded.text)
                self.assertFalse(any(0x80 <= ord(c) <= 0x9F for c in decoded.text))


class TestJsonIsUtf8(unittest.TestCase):
    def test_json_is_read_as_utf8_whatever_the_header_claims(self) -> None:
        # RFC 8259 fixes JSON to utf-8, and a charset parameter on it is
        # non-standard. Believing one would mojibake a valid document.
        decoded = decode_http_text(b'{"name": "' + UTF8_NAME + b'"}', "application/json; charset=iso-8859-1")
        self.assertIn("Tucumán", decoded.text)
        self.assertEqual("json-utf-8", decoded.source)

    def test_json_that_is_not_utf8_still_comes_back(self) -> None:
        decoded = decode_http_text(b'{"name": "' + CP1252_NAME + b'"}', "application/json")
        self.assertIn("Tucumán", decoded.text)
        self.assertEqual("cp1252", decoded.encoding)


class TestNothingIsDroppedQuietly(unittest.TestCase):
    def test_replacements_are_counted(self) -> None:
        # A byte that is not valid in the fallback either: the caller is told.
        decoded = decode_http_text(b"Name \x81\x8d more", "text/html")
        self.assertGreater(decoded.replacements, 0)
        self.assertEqual("fallback", decoded.source)

    def test_an_empty_body_is_not_an_error(self) -> None:
        self.assertEqual(DecodedText(text="", encoding="utf-8", source="empty"), decode_http_text(b""))

    def test_a_str_body_is_refused(self) -> None:
        # Passing already-decoded text would hide the very decision this makes.
        with self.assertRaises(TypeError):
            decode_http_text("already text")  # type: ignore[arg-type]


class TestTheSniffers(unittest.TestCase):
    def test_content_type_parsing(self) -> None:
        self.assertEqual("utf-8", charset_from_content_type("text/html; charset=UTF-8"))
        self.assertEqual("windows-1252", charset_from_content_type('text/html; charset="windows-1252"'))
        self.assertIsNone(charset_from_content_type("text/html"))
        self.assertIsNone(charset_from_content_type(None))
        # A charset Python has no codec for is not a charset we can use.
        self.assertIsNone(charset_from_content_type("text/html; charset=x-made-up"))

    def test_bom_detection(self) -> None:
        self.assertEqual("utf-8-sig", charset_from_bom(b"\xef\xbb\xbfhello"))
        self.assertEqual("utf-16-le", charset_from_bom(b"\xff\xfeh\x00"))
        self.assertIsNone(charset_from_bom(b"hello"))

    def test_meta_detection(self) -> None:
        self.assertEqual("utf-8", charset_from_html_meta(b'<meta charset="utf-8">'))
        self.assertEqual(
            "windows-1252",
            charset_from_html_meta(b'<meta http-equiv="Content-Type" content="text/html; charset=windows-1252">'),
        )
        self.assertIsNone(charset_from_html_meta(b"<html><body>no declaration</body></html>"))

    def test_a_late_meta_is_not_trusted(self) -> None:
        # The HTML standard requires the declaration early; a charset named after
        # kilobytes of content is not what the parser would have used.
        body = b"<html><head>" + b"<!-- padding -->" * 400 + b'<meta charset="windows-1252"></head>'
        self.assertIsNone(charset_from_html_meta(body))


class TestAgainstALocalServer(unittest.TestCase):
    """The same bytes over HTTP, through the client the admission crawler uses."""

    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-crawler-core"))
        from http_client import HttpClient  # noqa: E402

        cls.client = HttpClient()

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):  # noqa: D102
                pass

            def do_GET(self):  # noqa: D102
                if self.path == "/cp1252-html":
                    body, ctype = b"<html><body>" + CP1252_DASH + b"</body></html>", "text/html"
                elif self.path == "/declared":
                    body, ctype = CP1252_NAME, "text/plain; charset=windows-1252"
                else:
                    body, ctype = UTF8_DASH, "text/html; charset=utf-8"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        cls.port = sock.getsockname()[1]
        sock.close()
        cls.server = http.server.HTTPServer(("127.0.0.1", cls.port), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def test_the_client_no_longer_replaces_what_it_cannot_read_as_utf8(self) -> None:
        # Before: decode("utf-8", errors="replace") turned this into U+FFFD.
        body = self.client.get_text(self._url("/cp1252-html"))
        self.assertIn("–", body)
        self.assertNotIn("�", body)

    def test_the_client_honours_a_declared_charset(self) -> None:
        body = self.client.get_text(self._url("/declared"))
        self.assertEqual("Universidad Nacional de Tucumán", body)

    def test_the_payload_records_which_codec_read_it(self) -> None:
        from http_client import RequestSpec  # noqa: E402

        payload = self.client.send(RequestSpec(url=self._url("/declared")))
        self.assertEqual("windows-1252", payload.encoding)
        self.assertEqual("header", payload.encoding_source)

        guessed = self.client.send(RequestSpec(url=self._url("/cp1252-html")))
        self.assertEqual("fallback", guessed.encoding_source)


if __name__ == "__main__":
    unittest.main()
