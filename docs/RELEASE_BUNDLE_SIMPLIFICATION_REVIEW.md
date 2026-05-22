# Release Bundle Simplification Review

This document classifies the current `releases/v0.1-demo/` bundle artifacts,
identifies which are essential, which are supporting context, and which could
become optional in future releases.

It does not remove artifacts or change the bundle structure. It classifies,
explains, and recommends.

---

## Current Bundle Contents

The v0.1-demo bundle (as of MANIFEST.txt) contains 24 artifacts across five
categories:

1. Core release documentation
2. Operational confidence evidence
3. Diagnostic evidence
4. Snapshot data
5. Demo navigation

---

## Must-Exist Artifacts

These artifacts are required for any release or demo. A bundle without them
is incomplete.

| Artifact | Role | Why Required |
| --- | --- | --- |
| `smoke_release_output.txt` | Build and API smoke validation | Primary release evidence. Without it, no runtime health claim is grounded. |
| `demo_caveats.md` | Required presenter caveats | Demo-blocking if absent. Presenter cannot know what to disclose. |
| `operational_trust_summary.md` | Confidence rollup | Synthesizes all confidence signals. Release confidence claim depends on it. |
| `freshness_escalation.md` | Source freshness state | Required for honest demo claims about data recency. |
| `RELEASE_NOTES_v0.1.md` | Human-readable release summary | Expected artifact for any versioned release. |
| `MANIFEST.txt` | Bundle inventory | Required for bundle integrity verification. |
| `VERSION_SCOPE_v0.1.md` | Versioned feature scope | Defines what is and is not in scope for the release. |
| `diagnostics_summary.txt` | Runtime diagnostics summary | Evidence of system health at bundle time. |

---

## Supporting Context Artifacts

These artifacts add evidence depth. They are useful for demo preparation and
investigation but are not strictly required for a minimal release assertion.

| Artifact | Role | Notes |
| --- | --- | --- |
| `operational_summary.md` | Source-health detail | Provides per-source breakdown. Useful when trust summary shows source concerns. |
| `maintenance_readiness_summary.md` | Caveat/confidence detail | Useful for pre-release scoping and accepted limitations. |
| `drift_timeline.md` | Historical drift classification | Useful for trend questions. Not required for current-state release claim. |
| `operational_index_summary.md` | Handoff/onboarding summary | Useful for new operators receiving the bundle. Not a release gate artifact. |
| `DEMO_SCRIPT_v0.1.md` | Demo flow script | Required if a structured demo presentation is planned. |
| `SCREENSHOT_CHECKLIST_v0.1.md` | Screenshot verification | Required if screenshots are used in the demo or release documentation. |
| `RELEASE_STRUCTURE.md` | Bundle structure explanation | Orientation doc for bundle consumers. |
| `OPERATIONAL_ARTIFACTS.md` | Operational artifact index | Lists artifacts and their roles within the bundle. |

---

## Potentially Optional Future Artifacts

These artifacts serve valid roles in the current bundle but may become optional
or replaceable in future releases when operational confidence is higher.

| Artifact | Current Role | Future Consideration |
| --- | --- | --- |
| `latest_failure_summary.md` | Historical failure detail | As operational confidence grows, this may be superseded by `operational_trust_summary.md`. |
| `latest_status.json` | Compact snapshot pointer | Input artifact for report builders. May not need to be in a human-facing bundle. |
| `system_snapshot_*.json` | Point-in-time snapshot evidence | Two snapshots in the current bundle provide historical comparison. Future bundles may include only the most recent. |
| `screenshots/README.md` | Screenshot index | Only relevant if screenshots are included. May be removed when screenshots are not bundled. |

---

## Staleness Risk

Bundle report copies (`demo_caveats.md`, `operational_trust_summary.md`, etc.)
are accurate at bundle time. After the bundle is created, the live `reports/`
directory may be updated while bundle copies remain frozen.

**Implication:** When using a bundle for demo preparation, verify that the
bundle was created from the same snapshot state as the current live reports.
The `MANIFEST.txt` build timestamp provides the reference point.

If the live `reports/` directory shows more recent freshness or trust state,
use the live reports for the demo, not the bundle copies.

---

## Artifact Count Assessment

The current bundle contains 24 artifacts. This is manageable for a single-
operator RC-1 release. The risk of artifact count growth is low as long as
the bundle build script (`build_demo_bundle.sh`) does not add artifacts
automatically without a conscious addition decision.

Recommended bundle size discipline: keep the bundle under 30 artifacts. If
additions are needed, classify them against the must-exist / supporting /
optional hierarchy above before including.

---

## Recommendations

1. **Document staleness risk explicitly.** Add a one-line note to the bundle
   `OPERATIONAL_ARTIFACTS.md` stating that report copies are point-in-time and
   the live `reports/` directory is authoritative after bundle creation.

2. **Classify `latest_status.json` as input artifact.** It is a machine-readable
   input for report builders, not a human-reading artifact. Consider moving it
   to a `bundle-inputs/` folder in future bundles, or excluding it if no
   interactive tooling reads it from the bundle.

3. **Maintain the must-exist list in `build_demo_bundle.sh`.** The bundle script
   should verify that all must-exist artifacts are present before completing a
   bundle build. Missing must-exist artifacts should fail the bundle with a
   clear error.

4. **Do not add new summary reports to the bundle** without retiring an existing
   one. Each new report added to the bundle increases orientation time for the
   operator receiving the bundle.

---

## Boundary

This review classifies artifacts. It does not change the bundle structure,
remove any artifact, or modify `build_demo_bundle.sh`. All proposed changes
are recommendations for future maintenance windows.

See also:
- [REPORT_CRITICALITY.md](REPORT_CRITICALITY.md) — criticality classification
- [OPERATIONAL_RESTRAINT_GUIDELINES.md](OPERATIONAL_RESTRAINT_GUIDELINES.md) — when not to add artifacts
- [RC1_RELEASE_HYGIENE.md](RC1_RELEASE_HYGIENE.md) — artifact and ignore policy
