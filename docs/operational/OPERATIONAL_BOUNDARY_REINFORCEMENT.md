# Operational Boundary Reinforcement

This document explicitly names the capabilities that CrawlerNest has
intentionally NOT implemented, and explains why each is intentionally absent
at RC-1.

This is not a feature backlog. These are deliberate non-implementations that
reflect the architectural philosophy of the system at this stage.

---

## Intentionally Not Implemented

### Auto Remediation

**What it would mean:** Automatic detection of a degraded state followed by
automated corrective action (e.g., retrying a failed crawler, re-running
normalization, clearing stale cache entries).

**Why intentionally avoided at RC-1:**

Auto remediation blurs the line between observing a problem and changing the
system that produced it. At RC-1, preserving observable evidence of problems is
more valuable than hiding instability behind automatic retries. A masked repair
gives false confidence in both the demo and the operational record. Human review
of degraded states reveals real system limits.

---

### Runtime Self-Healing

**What it would mean:** The system detects its own failures at runtime
(connection drops, ranking timeouts, missing sources) and automatically
reconfigures, restarts, or falls back without operator involvement.

**Why intentionally avoided at RC-1:**

The RC-1 environment is localhost-bound and manually operated. Self-healing
requires verified runtime contracts that have not been established. Self-healing
logic that fails silently or heals to a wrong state is worse than a clear
failure. Explicit operator restart with manual smoke verification is the
appropriate recovery path for RC-1.

---

### Automatic Freshness Repair

**What it would mean:** When a source is detected as stale, the system
automatically triggers a re-crawl, re-normalization, or re-ingest of that
source.

**Why intentionally avoided at RC-1:**

Source freshness recovery requires human judgment: the source website may have
changed structure, the crawl may produce different schema, or the normalization
logic may need updating. An automatic rerun of a stale crawl may produce
incorrect data that passes automated validation but is wrong. The correct path
is the human-guided recovery plan in `docs/SOURCE_FRESHNESS_RECOVERY.md`.

---

### Autonomous Scoring Adjustment

**What it would mean:** Recommendation scores, ranking weights, or
aggregation parameters are adjusted at runtime based on observed data quality,
freshness signals, or user behavior.

**Why intentionally avoided at RC-1:**

Scoring behavior is frozen for RC-1 (see `docs/RC1_FREEZE_SCOPE.md`). Autonomous
adjustment would change demo-observable behavior without a deliberate decision,
making it impossible to explain or reproduce ranking output. All scoring changes
must be explicit, reviewed, and committed.

---

### Source Auto-Fallback

**What it would mean:** If a primary ranking source (e.g., QS) is unavailable
or stale, the system automatically substitutes data from a secondary source
or a cached older version without operator knowledge.

**Why intentionally avoided at RC-1:**

Silent fallback is a form of data mutation. The demo and release documentation
must accurately describe which sources are live and which are stale. An automatic
fallback that hides source gaps makes the demo claims incorrect. Operators must
explicitly know the source state and decide how to present it.

---

### Autonomous PR Generation

**What it would mean:** The system or an agent automatically creates pull
requests for configuration updates, dependency bumps, schema migrations, or
data fixes based on detected conditions.

**Why intentionally avoided at RC-1:**

Automated commits and PRs create a hidden change channel that bypasses human
review. At RC-1, all changes to the repository must be deliberate and
reviewable. Agent-assisted work is fine; agent-initiated commits without
explicit human intent are not.

---

### Runtime Observability Enforcement

**What it would mean:** An observability layer that enforces health thresholds
at runtime — blocking requests, throttling crawlers, or stopping operations when
metrics cross defined limits.

**Why intentionally avoided at RC-1:**

Runtime enforcement requires verified thresholds and thoroughly tested failure
modes. Misconfigured enforcement can make the system harder to operate than no
enforcement. At RC-1, all operational health signals are advisory and human-
directed. Enforcement belongs to a post-RC operational phase where runtime
contracts are well-established.

---

### Distributed Runtime Telemetry

**What it would mean:** A multi-node telemetry collection layer (metrics
server, aggregation pipeline, alerting rules) that observes runtime behavior
across processes.

**Why intentionally avoided at RC-1:**

CrawlerNest at RC-1 is a single-host localhost system. Distributed telemetry
infrastructure adds operational complexity, external service dependencies, and
maintenance burden that far exceeds the scale. The current snapshot and report
system provides adequate observability for the RC-1 scope.

---

### Automatic Signal Suppression

**What it would mean:** The system decides to suppress, downgrade, or hide
an escalation signal (e.g., a `critical` freshness state) because it has been
seen before, is "known," or does not affect demo flow.

**Why intentionally avoided at RC-1:**

Signal suppression hides operational truth from operators who need it. All
signals, including recurring ones, must remain visible. Operators may choose
to document a known limitation in `demo_caveats.md` and accept it, but the
system must not make that decision automatically.

---

## Summary Table

| Capability | Status | Primary Reason |
| --- | --- | --- |
| Auto remediation | Not implemented | Preserves observable evidence; avoids masked instability. |
| Runtime self-healing | Not implemented | Localhost RC-1 scope; explicit restart preferred. |
| Automatic freshness repair | Not implemented | Source recovery requires human judgment. |
| Autonomous scoring adjustment | Not implemented | Scoring is frozen for RC-1. |
| Source auto-fallback | Not implemented | Silent fallback creates incorrect demo claims. |
| Autonomous PR generation | Not implemented | All commits require explicit human intent. |
| Runtime observability enforcement | Not implemented | Advisory signals only; enforcement thresholds not verified. |
| Distributed runtime telemetry | Not implemented | Single-host scope; telemetry overhead exceeds scale. |
| Automatic signal suppression | Not implemented | All signals must remain visible to operators. |

---

## Boundary

These non-implementations are intentional design decisions for RC-1. They are
not gaps awaiting a future sprint. Any proposal to implement one of these
capabilities requires:

1. An explicit decision to leave RC-1 operational philosophy.
2. A named owner for the new runtime risk introduced.
3. A documented failure mode and recovery path.
4. Review against `docs/OPERATIONAL_RESTRAINT_GUIDELINES.md` criteria.

See also:
- [OPERATIONAL_RESTRAINT_GUIDELINES.md](OPERATIONAL_RESTRAINT_GUIDELINES.md)
- [RC1_FREEZE_SCOPE.md](../release/RC1_FREEZE_SCOPE.md)
- [OPERATIONAL_INTELLIGENCE_AUTOMATION.md](OPERATIONAL_INTELLIGENCE_AUTOMATION.md)
