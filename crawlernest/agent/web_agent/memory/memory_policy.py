from __future__ import annotations

import re
from dataclasses import dataclass, field

from .conversation_store import ConversationTurn

# ── Follow-up signal patterns ─────────────────────────────────────────────────
# When the user's wording signals they are referring back to a previously
# mentioned entity ("那它呢", "compare it", "跟 Cambridge 比較"), older turns
# that share entities with the current request become much more relevant.
_FOLLOWUP_PATTERNS: list[str] = [
    # CJK referential expressions
    r"它",
    r"那它",
    r"那所",
    r"那間",
    r"那個學校",
    r"那所學校",
    r"那大學",
    r"該校",
    r"那個",
    # English referential / comparative
    r"\bthat university\b",
    r"\bthat school\b",
    r"\bcompare it\b",
    r"\bcompared to\b",
    r"\bhow about it\b",
    r"\bwhat about it\b",
    r"\bvs\.?\b",
    r"\bversus\b",
    # CJK comparative constructions ("跟 X 比較", "和 X 相比" …)
    r"跟.{0,20}比較",
    r"和.{0,20}比較",
    r"與.{0,20}比較",
    r"跟.{0,20}相比",
    r"和.{0,20}相比",
    r"與.{0,20}相比",
]
_FOLLOWUP_RE = re.compile("|".join(_FOLLOWUP_PATTERNS), re.IGNORECASE)

# Maximum characters shown in content previews within debug output.
_PREVIEW_LENGTH = 80


def _extract_entity_tokens(text: str) -> set[str]:
    """Extract candidate entity tokens from *text* for overlap comparison.

    Three token classes — all normalised to lowercase:

    * All-uppercase acronyms (MIT, QS, THE, IELTS, ARWU) — 2+ characters
    * Initial-cap proper nouns (Oxford, Cambridge, Stanford) — 4+ total chars
    * CJK character sequences (牛津, 劍橋, 帝國理工) — 2+ hanzi

    Common English stop-words that happen to be capitalised at sentence start
    are suppressed via a small exclusion set.
    """
    _STOP = frozenset({"the", "and", "for", "with", "from", "that", "this",
                        "are", "was", "has", "have", "its", "it", "is",
                        "at", "in", "of", "to", "a", "an", "on", "or"})

    tokens: set[str] = set()

    # All-caps acronyms: MIT, QS, THE, IELTS — min 2 uppercase letters
    for word in re.findall(r"\b[A-Z]{2,}\b", text):
        lower = word.lower()
        if lower not in _STOP:
            tokens.add(lower)

    # Initial-cap proper nouns: Oxford, Cambridge — at least 4 total chars
    for word in re.findall(r"\b[A-Z][a-z]{3,}\b", text):
        lower = word.lower()
        if lower not in _STOP:
            tokens.add(lower)

    # CJK sequences of 2+ consecutive hanzi
    for seq in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        tokens.add(seq)

    return tokens


def _content_preview(text: str) -> str:
    """Return a safe truncated single-line preview of *text* for debug output."""
    cleaned = text.strip().replace("\n", " ")
    if len(cleaned) <= _PREVIEW_LENGTH:
        return cleaned
    return cleaned[:_PREVIEW_LENGTH] + "…"


# ── Debug report dataclasses ──────────────────────────────────────────────────

@dataclass
class TurnDebugInfo:
    """Debug record for a single conversation turn evaluated by MemoryPolicy."""

    role: str
    content_preview: str
    task_kind: str
    # Signals that were active and contributed to selection.
    # Empty list means no signals fired (turn was not selected or scored zero).
    selected_by: list[str]
    # Per-signal score contribution and total.
    score_breakdown: dict[str, int]
    # None → turn was selected.
    # Non-None → human-readable rejection reason:
    #   "score_zero"            — scored 0, not enough relevance signals
    #   "turn_budget_exceeded"  — had positive score but turn-count cap was full
    #   "char_budget_exceeded"  — was candidates but char budget ran out
    #   "outside_history_cap"  — older than max_turns * 2, never considered
    #   "memory_disabled"      — MemoryPolicy.enabled is False
    #   "no_history"           — session had no prior turns
    rejected_reason: str | None


@dataclass
class MemoryDebugReport:
    """Full observability report produced by MemoryPolicy.select_turns_debug()."""

    # ── Request signals ───────────────────────────────────────────────
    current_input_preview: str      # first 200 chars of the user's current message
    current_task_kind: str
    entity_tokens: list[str]        # sorted list of extracted entity tokens
    followup_detected: bool
    recent_entity_hint: str | None

    # ── Budget accounting ─────────────────────────────────────────────
    char_budget_max: int
    char_budget_used: int
    turn_budget_max_pairs: int      # = max_turns field
    selected_message_count: int     # individual messages (not pairs)
    memory_summary: dict[str, object]

    # ── Per-turn decisions ────────────────────────────────────────────
    selected_turns: list[TurnDebugInfo]
    rejected_turns: list[TurnDebugInfo]


# ── Main policy class ─────────────────────────────────────────────────────────

@dataclass(slots=True)
class MemoryPolicy:
    """Controls which conversation turns are surfaced to the LLM.

    Strategy — two-tier selection
    ─────────────────────────────

    **Tier 1 — always-recent (guaranteed)**
    The last ``always_recent`` individual messages are always injected.
    This gives the model immediate conversational continuity regardless of
    topic: the most recent exchange is almost always useful context.

    **Tier 2 — relevance-selected (earned)**
    Older turns (beyond the always-recent window) are scored against the
    current request.  Only turns with score > 0 are included, up to the
    remaining turn budget.

    Relevance is computed from three deterministic signals — no embeddings:

    * **Entity overlap** — shared proper-noun tokens between the current input
      and the prior turn's content.  Tokens include ASCII acronyms (MIT, QS),
      initial-cap proper nouns (Oxford, Cambridge), and CJK noun sequences
      (牛津, 劍橋).  Score: ``entity_weight`` pts per shared token.

    * **Task-kind match** — the prior turn was produced under the same
      ``task_kind`` as the current request (e.g. both are ``ranking_explain``).
      Score: ``kind_weight`` pts.

    * **Follow-up boost** — the current input contains referential or
      comparative language ("那它", "compare it", "跟 Cambridge 比較") **and**
      the prior turn shares at least one entity with the current input.
      This combination means the user is explicitly referring back to content
      in that turn.  Score: additional ``followup_boost`` pts.

    Turns with score 0 are excluded: they share no entities and are a
    different task type — injecting them would add irrelevant noise.
    The recommendation ↔ lookup boundary is handled automatically this way
    (a prior recommendation turn will score 0 against a ranking_explain query
    unless entities overlap).

    Hard limits (always applied after scoring)
    ──────────────────────────────────────────
    * Total injected messages ≤ ``max_turns * 2`` (user + assistant pairs)
    * Cumulative content ≤ ``max_context_chars`` characters; oldest trimmed first
    """

    max_turns: int = 6
    max_context_chars: int = 4000
    enabled: bool = True

    # Number of individual messages at the tail of history that are always kept.
    # Set to 2 (one full pair) so immediate context is never dropped.
    always_recent: int = 2

    # Scoring weights — exposed as fields so callers can tune without subclassing.
    entity_weight: int = 2
    kind_weight: int = 2
    followup_boost: int = 3
    carryover_entity_weight: int = 1

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #

    def select_turns(
        self,
        history: list[ConversationTurn],
        *,
        current_input: str = "",
        current_task_kind: str = "",
    ) -> list[ConversationTurn]:
        """Return the slice of *history* that should be injected into the prompt.

        Args:
            history: Full stored turn list for the session (chronological,
                oldest first).
            current_input: The user's current message.  Used to extract entity
                tokens and detect follow-up language.
            current_task_kind: The ``TaskRequest.kind`` for the current request.
                Used for task-kind relevance matching.

        Returns:
            A chronologically ordered list of :class:`ConversationTurn` objects
            that fits within all policy limits.  May be empty if history is empty
            or ``enabled`` is ``False``.
        """
        if not self.enabled or not history:
            return []

        # Pool: hard cap at max_turns * 2 individual messages (most recent).
        cap = self.max_turns * 2
        pool = history[-cap:] if len(history) > cap else list(history)

        # ── Tier 1: always-recent ──────────────────────────────────────
        recent_n = min(self.always_recent, len(pool))
        recent_turns: list[ConversationTurn] = pool[-recent_n:] if recent_n else []
        older_turns: list[ConversationTurn] = pool[:-recent_n] if recent_n else list(pool)

        # ── Tier 2: relevance-selected from older pool ─────────────────
        if older_turns and current_input:
            max_older = max(0, cap - recent_n)
            current_entities = _extract_entity_tokens(current_input)
            current_is_followup = bool(_FOLLOWUP_RE.search(current_input))
            recent_entity_hint = (
                self._extract_recent_entity_hint(pool)
                if not current_entities and current_is_followup
                else None
            )
            selected_older = self._select_relevant(
                turns=older_turns,
                current_input=current_input,
                current_task_kind=current_task_kind,
                max_count=max_older,
                recent_entity_hint=recent_entity_hint,
            )
        else:
            selected_older = []

        # Merge tiers: chronological order is preserved (older before recent).
        candidate = selected_older + recent_turns

        # ── Character budget: trim from oldest end ─────────────────────
        total_chars = 0
        kept: list[ConversationTurn] = []
        for turn in reversed(candidate):
            total_chars += len(turn.content)
            if total_chars > self.max_context_chars:
                break
            kept.append(turn)

        kept.reverse()
        return kept

    def select_turns_debug(
        self,
        history: list[ConversationTurn],
        *,
        current_input: str = "",
        current_task_kind: str = "",
    ) -> tuple[list[ConversationTurn], MemoryDebugReport]:
        """Instrumented variant of :meth:`select_turns` that also returns a
        :class:`MemoryDebugReport`.

        The selected turns returned are **identical** to what :meth:`select_turns`
        would return for the same arguments — the selection algorithm is
        unchanged.  The debug report adds per-turn scoring breakdowns and
        rejection reasons without affecting any selection decisions.

        This method is only called when ``debug=true`` is present in the request
        constraints.  Normal-mode requests always go through :meth:`select_turns`.
        """
        # ── Early exit ─────────────────────────────────────────────────
        if not self.enabled or not history:
            reason = "memory_disabled" if not self.enabled else "no_history"
            report = MemoryDebugReport(
                current_input_preview=current_input[:200],
                current_task_kind=current_task_kind,
                entity_tokens=[],
                followup_detected=False,
                recent_entity_hint=None,
                char_budget_max=self.max_context_chars,
                char_budget_used=0,
                turn_budget_max_pairs=self.max_turns,
                selected_message_count=0,
                memory_summary={
                    "selection_mode": "recent_only",
                    "primary_signals": ["always_recent"],
                    "selected_count": 0,
                    "rejected_count": len(history),
                    "ambiguity_level": "high",
                    "summary_text": "No strong signals found; fallback to recent turns.",
                },
                selected_turns=[],
                rejected_turns=[
                    TurnDebugInfo(
                        role=t.role,
                        content_preview=_content_preview(t.content),
                        task_kind=t.task_kind,
                        selected_by=[],
                        score_breakdown={"entity_overlap": 0, "kind_match": 0,
                                         "followup_boost": 0, "carryover_entity_match": 0, "total": 0},
                        rejected_reason=reason,
                    )
                    for t in history
                ],
            )
            return [], report

        # ── Compute request-level signals ──────────────────────────────
        entity_tokens = _extract_entity_tokens(current_input) if current_input else set()
        is_followup = bool(_FOLLOWUP_RE.search(current_input)) if current_input else False
        recent_entity_hint = (
            self._extract_recent_entity_hint(history)
            if not entity_tokens and is_followup
            else None
        )

        # ── Pool: hard cap ─────────────────────────────────────────────
        cap = self.max_turns * 2
        pool = history[-cap:] if len(history) > cap else list(history)
        pool_ids = {id(t) for t in pool}

        # ── Tier 1: always-recent ──────────────────────────────────────
        recent_n = min(self.always_recent, len(pool))
        recent_turns = pool[-recent_n:] if recent_n else []
        older_turns = pool[:-recent_n] if recent_n else list(pool)

        # ── Score all older turns ──────────────────────────────────────
        older_with_breakdown: list[tuple[ConversationTurn, dict[str, int]]] = [
            (t, self._score_turn_detailed(
                turn=t,
                entity_tokens=entity_tokens,
                current_task_kind=current_task_kind,
                is_followup=is_followup,
                recent_entity_hint=recent_entity_hint,
            ))
            for t in older_turns
        ]

        # ── Select from older: score > 0, top-N, restore chronological ─
        max_older = max(0, cap - recent_n)
        positive = [(t, bd) for t, bd in older_with_breakdown if bd["total"] > 0]
        positive.sort(key=lambda tb: tb[1]["total"], reverse=True)
        selected_older_pairs = positive[:max_older]
        selected_older_ids = {id(t) for t, _ in selected_older_pairs}
        older_order = {id(t): i for i, t in enumerate(older_turns)}
        selected_older_pairs.sort(key=lambda tb: older_order[id(tb[0])])

        # ── Build candidate list with breakdowns and is_recent flag ────
        # Type: list[ (turn, breakdown, is_recent) ]
        candidate_triples: list[tuple[ConversationTurn, dict[str, int], bool]] = []
        for t, bd in selected_older_pairs:
            candidate_triples.append((t, bd, False))
        for t in recent_turns:
            bd = self._score_turn_detailed(
                turn=t,
                entity_tokens=entity_tokens,
                current_task_kind=current_task_kind,
                is_followup=is_followup,
                recent_entity_hint=recent_entity_hint,
            )
            candidate_triples.append((t, bd, True))

        # ── Char budget trim (same algorithm as select_turns) ──────────
        total_chars = 0
        kept_triples: list[tuple[ConversationTurn, dict[str, int], bool]] = []
        budget_dropped_ids: set[int] = set()
        for triple in reversed(candidate_triples):
            t, bd, is_recent = triple
            total_chars += len(t.content)
            if total_chars > self.max_context_chars:
                # This turn and everything older in the reversed iteration
                # exceeds the budget — mark it and stop.
                budget_dropped_ids.add(id(t))
                # All remaining (older) candidates in the reversed loop are also dropped.
                # We break here so they never enter kept_triples; we'll catch them
                # in the rejected-turns assembly below via candidate_triples diff.
                break
            kept_triples.append(triple)

        kept_triples.reverse()
        selected_turns = [t for t, _, _ in kept_triples]
        selected_ids = {id(t) for t in selected_turns}
        char_budget_used = sum(len(t.content) for t in selected_turns)

        # ── Build debug info for selected turns ────────────────────────
        selected_infos: list[TurnDebugInfo] = []
        for t, bd, is_recent in kept_triples:
            signals: list[str] = []
            if is_recent:
                signals.append("always_recent")
            if bd["entity_overlap"] > 0:
                signals.append("entity_overlap")
            if bd["kind_match"] > 0:
                signals.append("kind_match")
            if bd["followup_boost"] > 0:
                signals.append("followup_boost")
            if bd["carryover_entity_match"] > 0:
                signals.append("carryover_entity_match")
            selected_infos.append(TurnDebugInfo(
                role=t.role,
                content_preview=_content_preview(t.content),
                task_kind=t.task_kind,
                selected_by=signals,
                score_breakdown=bd,
                rejected_reason=None,
            ))

        # ── Build debug info for rejected turns ────────────────────────
        rejected_infos: list[TurnDebugInfo] = []

        # 1. Turns outside the history cap (never evaluated).
        for t in history:
            if id(t) not in pool_ids:
                rejected_infos.append(TurnDebugInfo(
                    role=t.role,
                    content_preview=_content_preview(t.content),
                    task_kind=t.task_kind,
                    selected_by=[],
                    score_breakdown={"entity_overlap": 0, "kind_match": 0,
                                     "followup_boost": 0, "carryover_entity_match": 0, "total": 0},
                    rejected_reason="outside_history_cap",
                ))

        # 2. Older turns that didn't make it into selected_older_pairs.
        for t, bd in older_with_breakdown:
            if id(t) in selected_older_ids:
                continue  # selected — handled above
            reason = "score_zero" if bd["total"] == 0 else "turn_budget_exceeded"
            rejected_infos.append(TurnDebugInfo(
                role=t.role,
                content_preview=_content_preview(t.content),
                task_kind=t.task_kind,
                selected_by=[],
                score_breakdown=bd,
                rejected_reason=reason,
            ))

        # 3. Candidates that were eligible but dropped by char budget.
        candidate_ids = {id(t) for t, _, _ in candidate_triples}
        for t, bd, is_recent in candidate_triples:
            if id(t) in selected_ids:
                continue  # kept — handled above
            # Must be a char-budget casualty (only eligible turns land here).
            signals = []
            if is_recent:
                signals.append("always_recent")
            if bd["entity_overlap"] > 0:
                signals.append("entity_overlap")
            if bd["kind_match"] > 0:
                signals.append("kind_match")
            if bd["followup_boost"] > 0:
                signals.append("followup_boost")
            if bd["carryover_entity_match"] > 0:
                signals.append("carryover_entity_match")
            rejected_infos.append(TurnDebugInfo(
                role=t.role,
                content_preview=_content_preview(t.content),
                task_kind=t.task_kind,
                selected_by=signals,
                score_breakdown=bd,
                rejected_reason="char_budget_exceeded",
            ))

        report = MemoryDebugReport(
            current_input_preview=current_input[:200],
            current_task_kind=current_task_kind,
            entity_tokens=sorted(entity_tokens),
            followup_detected=is_followup,
            recent_entity_hint=recent_entity_hint,
            char_budget_max=self.max_context_chars,
            char_budget_used=char_budget_used,
            turn_budget_max_pairs=self.max_turns,
            selected_message_count=len(selected_turns),
            memory_summary=self._build_memory_summary(
                entity_tokens=entity_tokens,
                is_followup=is_followup,
                recent_entity_hint=recent_entity_hint,
                selected_infos=selected_infos,
                rejected_infos=rejected_infos,
            ),
            selected_turns=selected_infos,
            rejected_turns=rejected_infos,
        )
        return selected_turns, report

    def to_messages(
        self,
        turns: list[ConversationTurn],
    ) -> list[dict[str, str]]:
        """Convert :class:`ConversationTurn` objects to OpenAI-style message dicts."""
        return [{"role": t.role, "content": t.content} for t in turns]

    # ------------------------------------------------------------------ #
    # Internal: scoring                                                   #
    # ------------------------------------------------------------------ #

    def _select_relevant(
        self,
        *,
        turns: list[ConversationTurn],
        current_input: str,
        current_task_kind: str,
        max_count: int,
        recent_entity_hint: str | None = None,
    ) -> list[ConversationTurn]:
        """Score *turns*, keep those with score > 0, return up to *max_count*
        in original chronological order."""
        entity_tokens = _extract_entity_tokens(current_input)
        is_followup = bool(_FOLLOWUP_RE.search(current_input))

        scored: list[tuple[ConversationTurn, int]] = []
        for turn in turns:
            score = self._score_turn(
                turn=turn,
                entity_tokens=entity_tokens,
                current_task_kind=current_task_kind,
                is_followup=is_followup,
                recent_entity_hint=recent_entity_hint,
            )
            if score > 0:
                scored.append((turn, score))

        # Pick the highest-scoring turns, then restore chronological order.
        scored.sort(key=lambda ts: ts[1], reverse=True)
        selected = [t for t, _ in scored[:max_count]]
        turn_order = {id(t): i for i, t in enumerate(turns)}
        selected.sort(key=lambda t: turn_order[id(t)])
        return selected

    def _score_turn(
        self,
        *,
        turn: ConversationTurn,
        entity_tokens: set[str],
        current_task_kind: str,
        is_followup: bool,
        recent_entity_hint: str | None = None,
    ) -> int:
        """Return the total relevance score for *turn* (delegates to _score_turn_detailed)."""
        return self._score_turn_detailed(
            turn=turn,
            entity_tokens=entity_tokens,
            current_task_kind=current_task_kind,
            is_followup=is_followup,
            recent_entity_hint=recent_entity_hint,
        )["total"]

    def _score_turn_detailed(
        self,
        *,
        turn: ConversationTurn,
        entity_tokens: set[str],
        current_task_kind: str,
        is_followup: bool,
        recent_entity_hint: str | None = None,
    ) -> dict[str, int]:
        """Return a per-signal score breakdown for *turn*.

        Keys: ``entity_overlap``, ``kind_match``, ``followup_boost``,
        ``carryover_entity_match``, ``total``.
        Used by both the normal selection path (via ``_score_turn``) and the
        debug instrumentation path (``select_turns_debug``).
        """
        entity_overlap_val = 0
        kind_match_val = 0
        followup_boost_val = 0
        carryover_entity_match_val = 0
        overlap_count = 0
        turn_entities = _extract_entity_tokens(turn.content)

        # Entity overlap — only computed when the current input has entity tokens.
        if entity_tokens:
            overlap_count = len(entity_tokens & turn_entities)
            entity_overlap_val = overlap_count * self.entity_weight

        # Task-kind match
        if current_task_kind and turn.task_kind == current_task_kind:
            kind_match_val = self.kind_weight

        # Follow-up boost: referential language + entity evidence = highly relevant
        if is_followup and overlap_count > 0:
            followup_boost_val = self.followup_boost

        if (
            not entity_tokens
            and is_followup
            and recent_entity_hint
            and current_task_kind != "recommendation"
            and turn.task_kind != "recommendation"
            and recent_entity_hint in turn_entities
        ):
            carryover_entity_match_val = self.carryover_entity_weight

        total = (
            entity_overlap_val
            + kind_match_val
            + followup_boost_val
            + carryover_entity_match_val
        )
        return {
            "entity_overlap": entity_overlap_val,
            "kind_match": kind_match_val,
            "followup_boost": followup_boost_val,
            "carryover_entity_match": carryover_entity_match_val,
            "total": total,
        }

    def _extract_recent_entity_hint(
        self,
        history: list[ConversationTurn],
    ) -> str | None:
        assistant_seen = 0
        user_seen = 0

        for turn in reversed(history):
            if turn.role == "assistant" and assistant_seen < 2:
                assistant_seen += 1
                hint = self._pick_recent_entity_from_text(turn.content)
                if hint:
                    return hint

        for turn in reversed(history):
            if turn.role == "user" and user_seen < 2:
                user_seen += 1
                hint = self._pick_recent_entity_from_text(turn.content)
                if hint:
                    return hint

        return None

    def _pick_recent_entity_from_text(self, text: str) -> str | None:
        tokens = _extract_entity_tokens(text)
        if not tokens:
            return None

        lowered = text.lower()
        ranked = sorted(
            tokens,
            key=lambda token: (lowered.rfind(token.lower()), len(token)),
            reverse=True,
        )
        return ranked[0] if ranked else None

    def _build_memory_summary(
        self,
        *,
        entity_tokens: set[str],
        is_followup: bool,
        recent_entity_hint: str | None,
        selected_infos: list[TurnDebugInfo],
        rejected_infos: list[TurnDebugInfo],
    ) -> dict[str, object]:
        signal_counts: dict[str, int] = {
            "always_recent": 0,
            "entity_overlap": 0,
            "kind_match": 0,
            "followup_boost": 0,
            "carryover_entity_match": 0,
        }
        for info in selected_infos:
            for signal in info.selected_by:
                if signal in signal_counts:
                    signal_counts[signal] += 1

        primary_signals = [
            signal
            for signal, count in sorted(
                signal_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
            if count > 0
        ][:2]

        always_recent_count = signal_counts["always_recent"]
        relevance_count = (
            signal_counts["entity_overlap"]
            + signal_counts["kind_match"]
            + signal_counts["followup_boost"]
            + signal_counts["carryover_entity_match"]
        )
        if selected_infos and all(
            set(info.selected_by).issubset({"always_recent"}) for info in selected_infos
        ):
            selection_mode = "recent_only"
        elif relevance_count > always_recent_count:
            selection_mode = "relevance_heavy"
        else:
            selection_mode = "recent_plus_relevance"

        if signal_counts["entity_overlap"] > 0 or signal_counts["carryover_entity_match"] > 0:
            ambiguity_level = "low"
        elif not entity_tokens and is_followup and relevance_count > 0:
            ambiguity_level = "medium"
        elif not entity_tokens and relevance_count == 0:
            ambiguity_level = "high"
        else:
            ambiguity_level = "medium"

        if signal_counts["carryover_entity_match"] > 0 and signal_counts["entity_overlap"] == 0:
            if signal_counts["carryover_entity_match"] >= signal_counts["always_recent"]:
                summary_text = "Recent entity context was reused to resolve follow-up reference."
            else:
                summary_text = (
                    "Follow-up phrasing detected; recent entity context and conversation history were used."
                )
        elif entity_tokens and signal_counts["entity_overlap"] > 0:
            entity_preview = ", ".join(sorted(entity_tokens)[:2])
            summary_text = (
                f"Previous turns were selected due to shared entities ({entity_preview})."
            )
        elif not entity_tokens and is_followup and recent_entity_hint:
            summary_text = (
                "Follow-up phrasing detected; recent entity context and conversation history were used."
            )
        elif not entity_tokens and is_followup:
            summary_text = "Follow-up phrasing detected; recent context used to preserve meaning."
        elif not entity_tokens and relevance_count == 0:
            summary_text = "No strong signals found; fallback to recent turns."
        else:
            summary_text = "Memory relies on recent conversation continuity."

        return {
            "selection_mode": selection_mode,
            "primary_signals": primary_signals or ["always_recent"],
            "selected_count": len(selected_infos),
            "rejected_count": len(rejected_infos),
            "ambiguity_level": ambiguity_level,
            "summary_text": summary_text,
        }
