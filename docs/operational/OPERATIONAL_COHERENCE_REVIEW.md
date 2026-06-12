# Operational Coherence Review

This document analyzes the coherence, redundancy, terminology consistency, and
relationship stability across the current docs, reports, maintenance scripts,
release artifacts, trust summaries, and caveat summaries.

It does not consolidate or rewrite existing artifacts. It classifies coherence
strengths, identifies coherence risks, and recommends future cleanup
opportunities.

---

## Scope

Surfaces reviewed:

- `docs/` — 55+ operational documentation files
- `reports/` — 10 generated report files
- `scripts/` — 30+ operational and maintenance scripts
- `releases/v0.1-demo/` — release bundle artifacts
- Trust summary: `reports/operational_trust_summary.md`
- Caveat summary: `reports/demo_caveats.md`

---

## Coherence Strengths

### Terminology Consistency

The escalation vocabulary is consistent across the surface:

- `stale`, `degraded`, `critical`, `unavailable` — used consistently across
  freshness, snapshot, and trust reports.
- `readonly`, `no runtime mutation`, `no autonomous remediation` — used
  consistently as boundary markers.
- `RC-1` — used consistently to scope limitations.
- `localhost` — used consistently to describe the deployment posture.

This consistency means an operator who learns the vocabulary in one document can
read all others without re-learning terms.

### Readonly Boundary Coherence

All 30+ scripts carry readonly boundary documentation. The boundary statement
format is consistent:

> "This script reads X only. It does not connect to PostgreSQL, mutate application
> state, rerun crawlers, or change ranking output."

No script contradicts this boundary. No script has been found to perform an
undocumented write. This is a strong coherence foundation.

### Trust-Caveat-Smoke Triangle

The three primary pre-release artifacts are coherent:

| Artifact | Role | Input Sources |
| --- | --- | --- |
| `operational_trust_summary.md` | Confidence rollup | Maintenance readiness, caveats, freshness, snapshot |
| `demo_caveats.md` | Presenter obligations | Freshness escalation, operational summary, snapshot |
| `smoke_release_output.txt` | Build/runtime health | Runtime services, API endpoints |

These three artifacts answer different questions and do not duplicate each
other's conclusions. They are also the only three artifacts classified as
`critical` in `REPORT_CRITICALITY.md`.

### Report-to-Script Correspondence

Every key report has a clear generating script:

| Report | Script |
| --- | --- |
| `demo_caveats.md` | `build_demo_caveats.py` |
| `operational_trust_summary.md` | `build_operational_trust_summary.py` |
| `freshness_escalation.md` | `build_freshness_escalation.py` |
| `drift_timeline.md` | `build_drift_timeline.py` |
| `operational_summary.md` | `build_operational_summary.py` |
| `maintenance_readiness_summary.md` | `inspect_source_freshness.py` |
| `maintenance_calm_summary.md` | `build_maintenance_calm_summary.py` |
| `maintenance_navigation.md` | `build_maintenance_navigation.py` |

This 1:1 correspondence makes the surface easy to audit.

---

## Coherence Risks

### Risk 1: Freshness Semantics Divergence

`freshness` is defined in multiple documents with slightly different framings:

| Source | Freshness Definition |
| --- | --- |
| `SOURCE_HEALTH_MODEL.md` | State of a source: fresh/stale/unavailable based on age thresholds |
| `freshness_escalation.md` | Escalation state derived from snapshot aggregation age |
| `maintenance_readiness_summary.md` | `Freshness state` derived from source coverage and age |
| `FRESHNESS_CONSISTENCY_REVIEW.md` | Reviews divergences across these surfaces |
| `OPERATIONAL_VOCABULARY.md` | Canonical term definitions |

The risk: if a future operator updates one of these documents without updating
the others, the vocabulary consistency breaks down. `FRESHNESS_CONSISTENCY_REVIEW.md`
exists to document this risk, but updating it requires knowing it exists.

**Mitigation:** `OPERATIONAL_VOCABULARY.md` is the canonical term authority.
When freshness semantics change, update it first and let the other docs
follow.

---

### Risk 2: Confidence Language Proliferation

`confidence` appears in:

- `OPERATIONAL_CONFIDENCE_MODEL.md` — dimension definitions
- `CONFIDENCE_CONSISTENCY_REVIEW.md` — divergence review
- `operational_trust_summary.md` — per-dimension values
- `maintenance_readiness_summary.md` — `Operational confidence level`
- `MAINTENANCE_SIGNAL_CLARITY.md` — hierarchy guidance

Five surfaces carry confidence language. If one updates its confidence levels
or introduces a new dimension, the others may become stale. The risk is low
now because the values are derived mechanically (from snapshots), but will grow
if confidence semantics are manually adjusted.

---

### Risk 3: Phase Document Accumulation

Maintenance phases have produced a growing set of phase-specific artifacts:

- Phase validation scripts: 5 files (`validate_maintenance_*.py`)
- Phase-specific docs are now mixed with standing operational docs in `docs/`

Future operators cannot easily distinguish "one-time milestone evidence" from
"standing operational guidance." The docs directory has no sub-folder for
maintenance phase artifacts.

**Mitigation:** Consider a `docs/maintenance-phases/` sub-folder for phase
review documents. Standing operational docs remain in `docs/`.

---

### Risk 4: Release Bundle Copies vs Live Reports

The `releases/v0.1-demo/` bundle contains copies of 8 reports. These copies
are frozen at bundle-build time. The live `reports/` directory continues to
be updated. Over time:

- Live `reports/operational_trust_summary.md` may show different values than
  `releases/v0.1-demo/operational_trust_summary.md`.
- An operator checking the bundle copy will see stale confidence values.

`OPERATIONAL_ARTIFACTS.md` in the bundle documents this risk ("historical
release/demo artifacts, not runtime authority"). The `RELEASE_LIFECYCLE.md`
(new in Phase 5) provides per-report lifecycle documentation.

**Mitigation:** Always check live `reports/` for current state. Treat bundle
copies as historical evidence for the specific release, not the current state.

---

### Risk 5: Over-Referenced "See Also" Chains

Several Phase 4/5 documents include "See also" sections pointing to other
Phase 4/5 documents. This creates a documentation graph where every new doc
references every other new doc:

- `OPERATIONAL_RESTRAINT_GUIDELINES.md` → 3 "See also" links
- `MAINTENANCE_SUSTAINABILITY_REVIEW.md` → 2 links
- `SIGNAL_TO_NOISE_REVIEW.md` → 3 links
- `REPORT_CRITICALITY.md` → 3 links
- `OPERATIONAL_CALMNESS_REVIEW.md` → 3 links
- `MAINTENANCE_FATIGUE_REVIEW.md` → 3 links

Each link is valid. The aggregate effect is a dense reference graph where a
new operator following all "See also" links reads 8+ documents before reaching
actionable guidance.

**Mitigation:** The `MAINTENANCE_READING_MODES.md` document (Phase 5, Item 5)
provides a structured entry point that short-circuits the reference graph for
each operator role.

---

## Relationship Stability

### Stable Relationships

| Relationship | Stability |
| --- | --- |
| Snapshot → Reports (all builders read `latest_status.json`) | Stable |
| Smoke → Release bundle | Stable |
| Demo caveats → Trust summary (caveats are input) | Stable |
| Freshness escalation → Demo caveats (freshness state is input) | Stable |
| Maintenance overview → All report builders (orchestrates them) | Stable |

### Fragile Relationships

| Relationship | Fragility | Reason |
| --- | --- | --- |
| Phase docs → Operational docs (cross-references) | Low | Valid now; may become stale if operational docs are reorganized |
| Bundle copies → Live reports | Medium | Bundle copies diverge from live over time; no automatic sync |
| Validation scripts → Phase docs (each phase script validates the phase artifacts) | Low | Adding a new phase doc without updating the phase script leaves it unvalidated |

---

## Future Cleanup Opportunities

1. **`docs/maintenance-phases/` sub-folder** — Move phase-specific review docs
   (e.g., this document, `OPERATIONAL_CALMNESS_REVIEW.md`, Phase 4 restraint
   docs) into a sub-folder so they don't crowd the standing operational docs.
   Standing docs (`OPERATIONAL_RUNBOOK.md`, `SOURCE_HEALTH_MODEL.md`, etc.)
   remain at the `docs/` root.

2. **Bundle lifecycle annotation** — Add a one-line "frozen at bundle-build time"
   note to the header of each report copy in `releases/v0.1-demo/`. This can
   be added by `build_demo_bundle.sh` without changing the copy's content
   (prepend a comment line).

3. **Unified validation runner** — Replace the five `validate_maintenance_*.py`
   scripts with a single `validate_current_state.py` that validates the current
   surface without phase history. Phase scripts can be retained as archived
   evidence.

4. **Confidence vocabulary consolidation** — Define confidence levels in exactly
   one place (`OPERATIONAL_VOCABULARY.md`) and remove the duplicate definitions
   from `OPERATIONAL_CONFIDENCE_MODEL.md`. Keep the model document for
   interpretation guidance only.

---

## Conclusion

The operational surface is coherent at RC-1 scale. The primary risks are
gradual terminology drift (freshness and confidence semantics), bundle copy
staleness, and reference-graph density. None require immediate action. The
cleanup opportunities above are worthwhile backlog items for a future
maintenance window.

See also:
- [OPERATIONAL_VOCABULARY.md](OPERATIONAL_VOCABULARY.md) — canonical term authority
- [REPORT_RELATIONSHIPS.md](../data/REPORT_RELATIONSHIPS.md) — dependency map
- [REPORT_LIFECYCLE.md](../data/REPORT_LIFECYCLE.md) — lifecycle per report
- [MAINTENANCE_SUSTAINABILITY_REVIEW.md](MAINTENANCE_SUSTAINABILITY_REVIEW.md) — sustainability analysis
