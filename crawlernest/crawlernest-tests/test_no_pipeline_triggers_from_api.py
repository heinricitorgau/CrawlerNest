"""No pipeline triggers from the API layer.

CLAUDE.md makes the serving stack read-only, and the pipeline is started only by
an external scheduler (``run_pipeline scheduled-refresh``, see
``crawlernest/pipeline/commands/scheduled_refresh.py`` and
``deploy/scheduler/``). This fails if the Spring Boot API, the Next.js app or any
Python HTTP server gains a way to start a process or reach the pipeline.

The Python half was added on 2026-11-12, after ``crawlernest-api/src/app.py`` turned
out to be a FastAPI app with an unauthenticated ``POST /run-crawler``: never
deployed, startable by hand, and invisible to a test that read only Java and
TypeScript.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
JAVA_MAIN = REPO / "crawlernest" / "servise_for_java" / "src" / "main"
WEB_SRC = REPO / "crawlernest" / "crawlernest-web" / "src"

JAVA_FORBIDDEN = (
    re.compile(r"\bProcessBuilder\b"),
    re.compile(r"Runtime\.getRuntime\(\)\s*\.exec"),
    re.compile(r"run_pipeline|scheduled-refresh|crawlernest\.run_pipeline"),
    re.compile(r"@Scheduled\b"),
    re.compile(r"@EnableScheduling\b"),
)
PYTHON_ROOT = REPO / "crawlernest"
#: What makes a Python file an HTTP server: it imports a web framework or defines a request handler.
PY_HTTP_SERVER = re.compile(
    r"^\s*(?:from|import)\s+(?:fastapi|flask|starlette|aiohttp\.web|http\.server|wsgiref|uvicorn|tornado|bottle)\b"
    r"|BaseHTTPRequestHandler|ThreadingHTTPServer",
    re.MULTILINE,
)
PY_FORBIDDEN = (
    re.compile(r"^\s*(?:import\s+subprocess|from\s+subprocess\s+import)\b", re.MULTILINE),
    re.compile(r"\bos\.(?:system|popen|exec[lv]p?e?|spawn[lv]p?e?)\s*\("),
    re.compile(r"run_pipeline|scheduled-refresh|scheduled_refresh"),
)
#: Directories that hold no served code: tests start throwaway servers, and node_modules is not ours.
PY_SKIPPED_PARTS = {"crawlernest-tests", "tests", "node_modules", "__pycache__", ".venv"}

WEB_FORBIDDEN = (
    re.compile(r"""from\s+["'](?:node:)?child_process["']|require\(\s*["'](?:node:)?child_process["']\s*\)"""),
    re.compile(r"run_pipeline|scheduled-refresh"),
)


def _hits(root: Path, suffixes: tuple[str, ...], patterns) -> list[str]:
    hits = []
    for path in sorted(root.rglob("*")):
        if path.suffix not in suffixes or "node_modules" in path.parts or "__tests__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in patterns:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                hits.append(f"{path.relative_to(REPO)}:{line}: {match.group(0)}")
    return hits


class TestNoPipelineTriggersFromTheApiLayer(unittest.TestCase):
    def test_the_java_api_cannot_start_a_process_or_schedule_work(self):
        self.assertEqual([], _hits(JAVA_MAIN, (".java",), JAVA_FORBIDDEN))

    def test_the_web_app_cannot_start_a_process_or_name_the_pipeline(self):
        self.assertEqual([], _hits(WEB_SRC, (".ts", ".tsx", ".js", ".mjs"), WEB_FORBIDDEN))

    def test_no_python_http_server_can_start_a_process_or_name_the_pipeline(self):
        servers = [
            path for path in sorted(PYTHON_ROOT.rglob("*.py"))
            if not PY_SKIPPED_PARTS & set(path.parts)
            and PY_HTTP_SERVER.search(path.read_text(encoding="utf-8", errors="replace"))
        ]
        # The agent API must be among them, or the pattern has stopped recognising servers.
        self.assertIn(PYTHON_ROOT / "interfaces" / "api" / "agent_api" / "server.py", servers)
        hits = []
        for path in servers:
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in PY_FORBIDDEN:
                for match in pattern.finditer(text):
                    line = text.count("\n", 0, match.start()) + 1
                    hits.append(f"{path.relative_to(REPO)}:{line}: {match.group(0).strip()}")
        self.assertEqual([], hits)

    def test_the_scheduler_units_invoke_the_cli_not_an_http_endpoint(self):
        units = sorted((REPO / "deploy" / "scheduler").glob("*"))
        self.assertTrue(units, "deploy/scheduler holds the scheduler definition")
        text = "\n".join(p.read_text(encoding="utf-8") for p in units)
        self.assertIn("scheduled-refresh", text)
        self.assertNotRegex(text, r"https?://|curl\b|wget\b")


if __name__ == "__main__":
    unittest.main()
