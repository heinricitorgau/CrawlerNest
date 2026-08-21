from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Callable, Optional

from .alias_catalog import curated_alias_variants
from .normalizer import (
    expanded_transliteration,
    normalize_university_name,
    tokenize_for_blocking,
)
from .types import CanonicalProfile, EntityRecord, ResolutionResult

EmbeddingMatcher = Callable[[EntityRecord, list[CanonicalProfile]], Optional[tuple[int, float, str]]]


@dataclass(frozen=True)
class ResolverThresholds:
    fuzzy_accept: float = 0.88
    fuzzy_review: float = 0.82
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
        self._raw_display_name_index: dict[str, tuple[int, str]] = {}
        self._normalized_display_name_index: dict[str, tuple[int, str]] = {}
        self._raw_alias_index: dict[str, tuple[int, str]] = {}
        self._normalized_alias_index: dict[str, tuple[int, str]] = {}
        self._token_inverted: dict[str, set[int]] = defaultdict(set)
        self._country_index: dict[str, set[int]] = defaultdict(set)

        self._build_indexes(canonical_profiles)

    def _build_indexes(self, canonical_profiles: list[CanonicalProfile]) -> None:
        raw_display_candidates: dict[str, list[tuple[int, str]]] = defaultdict(list)
        normalized_display_candidates: dict[str, list[tuple[int, str]]] = defaultdict(list)
        raw_alias_candidates: dict[str, list[tuple[int, str]]] = defaultdict(list)
        normalized_alias_candidates: dict[str, list[tuple[int, str]]] = defaultdict(list)

        for profile in canonical_profiles:
            display_variants = {profile.display_name}
            stripped_display = self._strip_parenthetical_suffix(profile.display_name)
            if stripped_display and stripped_display != profile.display_name:
                display_variants.add(stripped_display)

            for display_variant in display_variants:
                raw_key = display_variant.strip().lower()
                norm_key = normalize_university_name(display_variant)
                if raw_key:
                    raw_display_candidates[raw_key].append((profile.canonical_university_id, profile.display_name))
                if norm_key:
                    normalized_display_candidates[norm_key].append((profile.canonical_university_id, profile.display_name))
                    for tok in tokenize_for_blocking(display_variant):
                        self._token_inverted[tok].add(profile.canonical_university_id)
                self._index_transliteration(
                    normalized_display_candidates,
                    display_variant,
                    profile.canonical_university_id,
                    profile.display_name,
                )

            aliases = {
                *profile.aliases,
                *curated_alias_variants(profile.display_name, profile.aliases),
            }
            for alias in aliases:
                stripped_alias = self._strip_parenthetical_suffix(alias)
                alias_variants = {alias}
                if stripped_alias and stripped_alias != alias:
                    alias_variants.add(stripped_alias)

                for alias_variant in alias_variants:
                    raw_key = alias_variant.strip().lower()
                    norm_key = normalize_university_name(alias_variant)
                    if raw_key:
                        raw_alias_candidates[raw_key].append((profile.canonical_university_id, alias_variant))
                    if norm_key:
                        normalized_alias_candidates[norm_key].append((profile.canonical_university_id, alias_variant))
                        for tok in tokenize_for_blocking(alias_variant):
                            self._token_inverted[tok].add(profile.canonical_university_id)
                    self._index_transliteration(
                        normalized_alias_candidates,
                        alias_variant,
                        profile.canonical_university_id,
                        alias_variant,
                    )
            if profile.country_hint:
                for country_variant in self._country_variants(profile.country_hint):
                    self._country_index[country_variant].add(profile.canonical_university_id)

        self._raw_display_name_index = self._finalize_unique_index(raw_display_candidates)
        self._normalized_display_name_index = self._finalize_unique_index(normalized_display_candidates)
        self._raw_alias_index = self._finalize_unique_index(raw_alias_candidates)
        self._normalized_alias_index = self._finalize_unique_index(normalized_alias_candidates)

    def _index_transliteration(
        self,
        candidates: dict[str, list[tuple[int, str]]],
        text: str,
        canonical_id: int,
        matched_alias: str,
    ) -> None:
        """
        Also index `text` under the spelled-out transliteration convention, so
        "München" is reachable from a source that writes "Muenchen".

        Any key that ends up pointing at more than one canonical university is
        dropped by _finalize_unique_index, so an expansion that collides with
        an unrelated name silently disables itself rather than merging two
        universities.
        """
        expanded_key = expanded_transliteration(text)
        if not expanded_key:
            return
        candidates[expanded_key].append((canonical_id, matched_alias))
        for tok in expanded_key.split():
            self._token_inverted[tok].add(canonical_id)

    def resolve_batch(self, records: list[EntityRecord]) -> list[ResolutionResult]:
        return [self.resolve_one(r) for r in records]

    def resolve_one(self, record: EntityRecord) -> ResolutionResult:
        raw_name = (record.university_name or "").strip()
        raw_key = raw_name.lower()
        norm_name = normalize_university_name(raw_name)

        # The record may itself be written under either convention, so both
        # keys are tried. The suffix keeps the two apart in the reported
        # method, which is how the transliteration path stays measurable.
        norm_expanded = expanded_transliteration(raw_name)
        norm_lookups: tuple[tuple[str, str], ...] = (
            ((norm_name, ""),)
            if not norm_expanded
            else ((norm_name, ""), (norm_expanded, "_transliterated"))
        )

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
                metadata=self._build_metadata(
                    record=record,
                    canonical_id=cid,
                    matched_alias=matched_alias,
                    normalized_name=norm_name,
                    candidate_count=1,
                    score=1.0,
                ),
            )

        # Stage 2: Normalized alias exact
        for lookup_key, method_suffix in norm_lookups:
            norm_exact = self._normalized_alias_index.get(lookup_key)
            if not norm_exact:
                continue
            cid, matched_alias = norm_exact
            return ResolutionResult(
                source_name=record.source_name,
                source_entity_id=record.source_entity_id,
                canonical_university_id=cid,
                matched_alias=matched_alias,
                confidence_score=0.98,
                matching_method=f"normalized{method_suffix}",
                candidate_count=1,
                metadata=self._build_metadata(
                    record=record,
                    canonical_id=cid,
                    matched_alias=matched_alias,
                    normalized_name=norm_name,
                    candidate_count=1,
                    score=0.98,
                ),
            )

        # Stage 3: Exact canonical display-name match
        exact_display = self._raw_display_name_index.get(raw_key)
        if exact_display:
            cid, matched_alias = exact_display
            return ResolutionResult(
                source_name=record.source_name,
                source_entity_id=record.source_entity_id,
                canonical_university_id=cid,
                matched_alias=matched_alias,
                confidence_score=0.99,
                matching_method="exact_display",
                candidate_count=1,
                metadata=self._build_metadata(
                    record=record,
                    canonical_id=cid,
                    matched_alias=matched_alias,
                    normalized_name=norm_name,
                    candidate_count=1,
                    score=0.99,
                ),
            )

        # Stage 4: Normalized canonical display-name match
        for lookup_key, method_suffix in norm_lookups:
            normalized_display = self._normalized_display_name_index.get(lookup_key)
            if not normalized_display:
                continue
            cid, matched_alias = normalized_display
            return ResolutionResult(
                source_name=record.source_name,
                source_entity_id=record.source_entity_id,
                canonical_university_id=cid,
                matched_alias=matched_alias,
                confidence_score=0.97,
                matching_method=f"normalized_display{method_suffix}",
                candidate_count=1,
                metadata=self._build_metadata(
                    record=record,
                    canonical_id=cid,
                    matched_alias=matched_alias,
                    normalized_name=norm_name,
                    candidate_count=1,
                    score=0.97,
                ),
            )

        # Stage 5: Fuzzy on blocked candidates
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
                    metadata=self._build_metadata(
                        record=record,
                        canonical_id=resolved_id,
                        matched_alias=matched_alias,
                        normalized_name=norm_name,
                        candidate_count=len(blocked),
                        score=round(score, 4),
                    ),
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
                        metadata=self._build_metadata(
                            record=record,
                            canonical_id=cid,
                            matched_alias=matched_alias,
                            normalized_name=norm_name,
                            candidate_count=len(candidates),
                            score=round(score, 4),
                        ),
                    )

        return ResolutionResult(
            source_name=record.source_name,
            source_entity_id=record.source_entity_id,
            canonical_university_id=None,
            matched_alias=None,
            confidence_score=0.0,
            matching_method="unresolved",
            candidate_count=len(blocked),
            metadata=self._build_metadata(
                record=record,
                canonical_id=None,
                matched_alias=None,
                normalized_name=norm_name,
                candidate_count=len(blocked),
                score=0.0,
            ),
        )

    def _build_metadata(
        self,
        *,
        record: EntityRecord,
        canonical_id: int | None,
        matched_alias: str | None,
        normalized_name: str,
        candidate_count: int,
        score: float,
    ) -> dict[str, object]:
        metadata: dict[str, object] = {
            "normalized_name": normalized_name,
            "token_overlap": round(self._token_overlap(record.university_name, matched_alias), 4),
            "candidate_count_hint": candidate_count,
        }
        if canonical_id is not None:
            profile = self._profiles_by_id.get(canonical_id)
            if profile and profile.country_hint:
                metadata["matched_country_hint"] = profile.country_hint
                country_mismatch = self._country_mismatch(record.country_hint, profile.country_hint)
                metadata["country_mismatch"] = country_mismatch
                metadata["suspicious_merge"] = bool(
                    country_mismatch or (score < self.thresholds.fuzzy_accept and metadata["token_overlap"] < 0.35)
                )
        else:
            metadata["country_mismatch"] = False
            metadata["suspicious_merge"] = False
        return metadata

    @staticmethod
    def _finalize_unique_index(candidates: dict[str, list[tuple[int, str]]]) -> dict[str, tuple[int, str]]:
        out: dict[str, tuple[int, str]] = {}
        for key, values in candidates.items():
            distinct_ids = {cid for cid, _ in values}
            if len(distinct_ids) != 1:
                continue
            cid = next(iter(distinct_ids))
            matched_alias = sorted({alias for _, alias in values}, key=lambda alias: (len(alias), alias))[0]
            out[key] = (cid, matched_alias)
        return out

    def _candidate_ids(self, record: EntityRecord, normalized_name: str) -> list[int]:
        # Token blocking. The per-candidate hit count is kept so that the
        # max_fuzzy_candidates cap below keeps the best-overlapping candidates
        # instead of an arbitrary slice of a set.
        query_tokens = set(tokenize_for_blocking(normalized_name))
        expanded_query = expanded_transliteration(record.university_name)
        if expanded_query:
            query_tokens.update(expanded_query.split())

        token_hits: dict[int, int] = defaultdict(int)
        for tok in query_tokens:
            for cid in self._token_inverted.get(tok, ()):
                token_hits[cid] += 1
        token_union: set[int] = set(token_hits) if query_tokens else set(self._profiles_by_id.keys())

        # Country blocking (if provided).
        # Fix R3: if the intersection is empty (country stored in a different format),
        # fall back to the full token_union rather than returning no candidates, which
        # would force an unresolved result even for a strong name match.
        if record.country_hint:
            country_set: set[int] = set()
            for country_variant in self._country_variants(record.country_hint):
                country_set.update(self._country_index.get(country_variant, set()))
            if country_set:
                narrowed = token_union.intersection(country_set) if token_union else country_set
                token_union = narrowed if narrowed else token_union

        if not token_union:
            return []
        # Rank before truncating. `list(set)` ordering is arbitrary, so the old
        # slice could drop the correct candidate for any name whose token
        # neighbourhood exceeds the cap - which is most US universities.
        ids = sorted(token_union, key=lambda cid: (-token_hits.get(cid, 0), cid))
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
                alias_variants = [alias]
                stripped_alias = self._strip_parenthetical_suffix(alias)
                if stripped_alias and stripped_alias != alias:
                    alias_variants.append(stripped_alias)

                best_alias_score: Optional[float] = None
                for alias_variant in alias_variants:
                    alias_norm = normalize_university_name(alias_variant)
                    if not alias_norm:
                        continue
                    seq = SequenceMatcher(None, normalized_name, alias_norm).ratio()
                    alias_tokens = set(tokenize_for_blocking(alias_variant))
                    token_jaccard = (
                        len(record_tokens & alias_tokens) / len(record_tokens | alias_tokens)
                        if record_tokens or alias_tokens
                        else 0.0
                    )
                    score = 0.75 * seq + 0.25 * token_jaccard
                    if best_alias_score is None or score > best_alias_score:
                        best_alias_score = score

                if best_alias_score is None:
                    continue
                score = best_alias_score
                if best is None or score > best[2]:
                    best = (cid, alias, score)
        return best

    @staticmethod
    def _token_overlap(raw_name: str, matched_alias: str | None) -> float:
        if not matched_alias:
            return 0.0
        left = set(tokenize_for_blocking(raw_name))
        right = set(tokenize_for_blocking(matched_alias))
        if not left and not right:
            return 0.0
        return len(left & right) / max(len(left | right), 1)

    def _country_mismatch(self, record_country: str | None, profile_country: str | None) -> bool:
        if not record_country or not profile_country:
            return False
        record_variants = set(self._country_variants(record_country))
        profile_variants = set(self._country_variants(profile_country))
        return record_variants.isdisjoint(profile_variants)

    @staticmethod
    def _strip_parenthetical_suffix(alias: str) -> str:
        return re.sub(r"\s*\([^)]*\)\s*$", "", str(alias or "")).strip()

    @staticmethod
    def _country_variants(country_hint: str) -> list[str]:
        base = str(country_hint or "").strip().lower()
        if not base:
            return []
        variant_groups = {
            "china": ["china", "china (mainland)", "china mainland"],
            "united states": ["united states", "united states of america", "usa"],
            "south korea": ["south korea", "korea, south", "republic of korea"],
            "taiwan": ["taiwan", "taiwan (province of china)"],
            "hong kong": ["hong kong", "hong kong sar", "hong kong s.a.r."],
            "iran": ["iran", "iran (islamic republic of)"],
            "russia": ["russia", "russian federation"],
        }
        for variants in variant_groups.values():
            if base in variants:
                return variants
        return [base]
