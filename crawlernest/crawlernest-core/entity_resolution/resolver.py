from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Callable, Optional

from .normalizer import normalize_university_name, tokenize_for_blocking
from .types import CanonicalProfile, EntityRecord, ResolutionResult

EmbeddingMatcher = Callable[[EntityRecord, list[CanonicalProfile]], Optional[tuple[int, float, str]]]


@dataclass(frozen=True)
class ResolverThresholds:
    fuzzy_accept: float = 0.93
    fuzzy_review: float = 0.88
    embedding_accept: float = 0.90
    embedding_review: float = 0.84


class EntityResolver:
    """
    Multi-stage resolver:
    1) exact alias match
    2) normalized exact match
    3) fuzzy match on blocked candidates
    4) optional embedding matcher
    """

    def __init__(
        self,
        canonical_profiles: list[CanonicalProfile],
        thresholds: Optional[ResolverThresholds] = None,
        embedding_matcher: Optional[EmbeddingMatcher] = None,
        max_fuzzy_candidates: int = 120,
    ):
        self.thresholds = thresholds or ResolverThresholds()
        self.embedding_matcher = embedding_matcher
        self.max_fuzzy_candidates = max(10, int(max_fuzzy_candidates))

        self._profiles_by_id = {p.canonical_university_id: p for p in canonical_profiles}
        self._raw_alias_index: dict[str, tuple[int, str]] = {}
        self._normalized_alias_index: dict[str, tuple[int, str]] = {}
        self._token_inverted: dict[str, set[int]] = defaultdict(set)
        self._country_index: dict[str, set[int]] = defaultdict(set)

        self._build_indexes(canonical_profiles)

    def _build_indexes(self, canonical_profiles: list[CanonicalProfile]) -> None:
        for profile in canonical_profiles:
            aliases = {profile.display_name, *profile.aliases}
            for alias in aliases:
                raw_key = alias.strip().lower()
                norm_key = normalize_university_name(alias)
                if raw_key:
                    self._raw_alias_index.setdefault(raw_key, (profile.canonical_university_id, alias))
                if norm_key:
                    self._normalized_alias_index.setdefault(norm_key, (profile.canonical_university_id, alias))
                    for tok in tokenize_for_blocking(alias):
                        self._token_inverted[tok].add(profile.canonical_university_id)
            if profile.country_hint:
                self._country_index[profile.country_hint.strip().lower()].add(profile.canonical_university_id)

    def resolve_batch(self, records: list[EntityRecord]) -> list[ResolutionResult]:
        return [self.resolve_one(r) for r in records]

    def resolve_one(self, record: EntityRecord) -> ResolutionResult:
        raw_name = (record.university_name or "").strip()
        raw_key = raw_name.lower()
        norm_name = normalize_university_name(raw_name)

        # Stage 1: Exact
        exact = self._raw_alias_index.get(raw_key)
        if exact:
            cid, matched_alias = exact
            return ResolutionResult(
                source_name=record.source_name,
                source_entity_id=record.source_entity_id,
                canonical_university_id=cid,
                matched_alias=matched_alias,
                confidence_score=1.0,
                matching_method="exact",
                candidate_count=1,
                metadata={"normalized_name": norm_name},
            )

        # Stage 2: Normalized exact
        norm_exact = self._normalized_alias_index.get(norm_name)
        if norm_exact:
            cid, matched_alias = norm_exact
            return ResolutionResult(
                source_name=record.source_name,
                source_entity_id=record.source_entity_id,
                canonical_university_id=cid,
                matched_alias=matched_alias,
                confidence_score=0.98,
                matching_method="normalized",
                candidate_count=1,
                metadata={"normalized_name": norm_name},
            )

        # Stage 3: Fuzzy on blocked candidates
        blocked = self._candidate_ids(record, norm_name)
        if blocked:
            fuzzy = self._fuzzy_best_match(record, blocked, norm_name)
            if fuzzy is not None:
                candidate_id, matched_alias, score = fuzzy
                method = "fuzzy" if score >= self.thresholds.fuzzy_accept else "fuzzy_review"
                resolved_id = candidate_id if score >= self.thresholds.fuzzy_review else None
                return ResolutionResult(
                    source_name=record.source_name,
                    source_entity_id=record.source_entity_id,
                    canonical_university_id=resolved_id,
                    matched_alias=matched_alias,
                    confidence_score=round(score, 4),
                    matching_method=method if resolved_id else "unresolved",
                    candidate_count=len(blocked),
                    metadata={"normalized_name": norm_name},
                )

        # Stage 4: embedding (optional, pluggable)
        if self.embedding_matcher:
            candidates = [self._profiles_by_id[cid] for cid in blocked] if blocked else list(self._profiles_by_id.values())
            emb = self.embedding_matcher(record, candidates)
            if emb:
                cid, score, matched_alias = emb
                if score >= self.thresholds.embedding_review:
                    method = "embedding" if score >= self.thresholds.embedding_accept else "embedding_review"
                    return ResolutionResult(
                        source_name=record.source_name,
                        source_entity_id=record.source_entity_id,
                        canonical_university_id=cid,
                        matched_alias=matched_alias,
                        confidence_score=round(score, 4),
                        matching_method=method,
                        candidate_count=len(candidates),
                        metadata={"normalized_name": norm_name},
                    )

        return ResolutionResult(
            source_name=record.source_name,
            source_entity_id=record.source_entity_id,
            canonical_university_id=None,
            matched_alias=None,
            confidence_score=0.0,
            matching_method="unresolved",
            candidate_count=len(blocked),
            metadata={"normalized_name": norm_name},
        )

    def _candidate_ids(self, record: EntityRecord, normalized_name: str) -> list[int]:
        # Token blocking
        token_sets = [self._token_inverted.get(tok, set()) for tok in tokenize_for_blocking(normalized_name)]
        token_union: set[int] = set().union(*token_sets) if token_sets else set(self._profiles_by_id.keys())

        # Country blocking (if provided)
        if record.country_hint:
            country_set = self._country_index.get(record.country_hint.strip().lower(), set())
            if country_set:
                token_union = token_union.intersection(country_set) if token_union else country_set

        if not token_union:
            return []
        ids = list(token_union)
        return ids[: self.max_fuzzy_candidates]

    def _fuzzy_best_match(
        self,
        record: EntityRecord,
        candidate_ids: list[int],
        normalized_name: str,
    ) -> Optional[tuple[int, str, float]]:
        best: Optional[tuple[int, str, float]] = None
        record_tokens = set(tokenize_for_blocking(record.university_name))

        for cid in candidate_ids:
            profile = self._profiles_by_id[cid]
            alias_pool = (profile.display_name, *profile.aliases)
            for alias in alias_pool:
                alias_norm = normalize_university_name(alias)
                if not alias_norm:
                    continue
                seq = SequenceMatcher(None, normalized_name, alias_norm).ratio()
                alias_tokens = set(tokenize_for_blocking(alias))
                token_jaccard = (
                    len(record_tokens & alias_tokens) / len(record_tokens | alias_tokens)
                    if record_tokens or alias_tokens
                    else 0.0
                )
                score = 0.75 * seq + 0.25 * token_jaccard
                if best is None or score > best[2]:
                    best = (cid, alias, score)
        return best
