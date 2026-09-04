"""An LLM second opinion on whether an explanation stays inside its evidence.

The mechanical checker in ``faithfulness.py`` is the primary signal and stays
authoritative: on the golden set it has perfect precision, so when it fires the
explanation is wrong. What it cannot do is express failures that have no rule --
a caveat reproduced verbatim and undercut by the next sentence, a causal claim
the evidence does not contain, a subject rank presented as a global one, a rank
described as climbing over a corpus that holds a single year. Measured on the
55-case golden set -- the run recorded in
``crawlernest-autoeval/reports/judge_calibration_qwen2.5-7b.json`` -- the rules
reach 0.472 of actual unfaithfulness and this judge reaches 0.667; either
flagging reaches 0.833, at judge precision 0.960. That measurement is what this
module exists on the strength of, not an intuition that a judge would help.

Those figures describe the golden set as it stood at that run. The two temporal
cases added since (faith-122, faith-123) post-date it and are not in them; the
judge has not been re-calibrated against a set that contains them.

Opt-in and failure-tolerant by construction. With ``WEB_AGENT_JUDGE_BASE_URL``
unset the judge is simply absent and generation behaves exactly as it did before
it existed. If the endpoint is slow, unreachable or replies with something
unparseable, :meth:`LlmJudge.review` returns ``None`` -- "no opinion" -- rather
than guessing. A verification layer that fails closed on a network blip would
degrade explanations for reasons that have nothing to do with their content.

The prompt lives here rather than in the calibration runner so that what was
measured and what is deployed cannot drift apart.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

#: Instruction given to the judge. Changing it invalidates the calibration in
#: crawlernest/crawlernest-autoeval/reports/, so re-run that first.
JUDGE_SYSTEM = """You audit explanations produced from a fixed block of evidence.

An explanation is FAITHFUL when everything it asserts is supported by the
evidence: every number appears in the evidence or follows from the number of
items given, every institution named appears in the evidence, and every caveat
supplied with the evidence is reproduced without being softened or dropped.

An explanation is UNFAITHFUL when it invents a figure, invents an institution,
rescales or transforms a value, drops a caveat, or restates a caveat in weaker
language.

Answer with a single JSON object and nothing else:
{"faithful": true or false, "reason": "one short sentence"}"""

_DEFAULT_TIMEOUT = 20.0
_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(frozen=True)
class JudgeVerdict:
    faithful: bool
    reason: str
    model_name: str


def build_review_prompt(
    *,
    explanation: str,
    items: list[dict[str, Any]] | None = None,
    caveats: list[str] | None = None,
    evidence: Any = None,
) -> str:
    """The user message: the evidence the explanation was supposed to stay inside."""
    return json.dumps(
        {
            "evidence_items": items or [],
            "caveats_supplied": caveats or [],
            "other_evidence": evidence,
            "explanation_under_review": explanation,
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


class LlmJudge:
    """OpenAI-compatible judge client. Absent unless explicitly configured."""

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url if base_url is not None
                         else os.getenv("WEB_AGENT_JUDGE_BASE_URL", "")).strip()
        self.model_name = (model_name if model_name is not None
                           else os.getenv("WEB_AGENT_JUDGE_MODEL", "")).strip() or "qwen2.5:7b-instruct"
        self.api_key = (api_key if api_key is not None
                        else os.getenv("WEB_AGENT_JUDGE_API_KEY", "")).strip()
        self.timeout = timeout if timeout is not None else _env_float(
            "WEB_AGENT_JUDGE_TIMEOUT", _DEFAULT_TIMEOUT
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)

    def review(
        self,
        *,
        explanation: str,
        items: list[dict[str, Any]] | None = None,
        caveats: list[str] | None = None,
        evidence: Any = None,
    ) -> JudgeVerdict | None:
        """A verdict, or ``None`` for "no opinion".

        ``None`` covers every way this can fail to produce an answer: not
        configured, unreachable, timed out, or a reply that is not the JSON it
        was asked for. Callers treat it as absence of a signal, never as
        approval.
        """
        if not self.is_configured or not explanation.strip():
            return None

        payload = json.dumps({
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": build_review_prompt(
                    explanation=explanation, items=items, caveats=caveats, evidence=evidence)},
            ],
            "temperature": 0,
            "max_tokens": 200,
        }).encode("utf-8")

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request = urllib.request.Request(
            self.base_url.rstrip("/") + "/chat/completions", data=payload, headers=headers
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return None

        try:
            text = body["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            return None

        match = _JSON_BLOCK.search(text)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except ValueError:
            return None
        if not isinstance(parsed.get("faithful"), bool):
            return None

        return JudgeVerdict(
            faithful=parsed["faithful"],
            reason=str(parsed.get("reason", "")).strip()[:300],
            model_name=self.model_name,
        )
