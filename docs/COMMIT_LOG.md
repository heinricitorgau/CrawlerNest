# CrawlerNest — 完整 Commit 紀錄

產生於 2026-09-04，涵蓋所有分支（`git log --all`）。每筆附上該 commit 的檔案變更統計。

- **Commit 總數**：366
- **期間**：2026-03-16 ~ 2026-09-04
- **主分支**：`main`

## 欄位說明

| 欄位 | 意義 |
|---|---|
| Commit | 短 hash；分支／tag 標記以粗體附在說明後 |
| 檔案 | 該 commit 變更的檔案數 |
| +/− | 新增／刪除行數 |
| 說明 | commit subject（第一行） |

Merge commit 的統計為 `—`：預設 diff 對 merge 不輸出 stat。

## 重現指令

```bash
git -c safe.directory='*' log --all --date=short --shortstat \
  --pretty=format:'%h %ad %an %d %s'
```

repo 位於 WSL 檔案系統、git 由 Windows 端執行時，未加 `-c safe.directory='*'` 會出現 `dubious ownership` 錯誤。

本檔由 `scripts/generate_commit_log.py` 產生；請勿手動編輯。

---

## 2026-09

| Commit | 日期 | 作者 | 檔案 | +/− | 說明 |
|---|---|---|---|---|---|
| `708f751` | 2026-09-04 | heinricitorgau | 1 | +48 / −0 | Retire aggregated rows whose university has dropped out of the universe **[main]** |
| `2620a11` | 2026-09-04 | heinricitorgau | 1 | +15 / −20 | Judge the THE and ARWU fuzzy backlog the canonical reseed produced |
| `24eae13` | 2026-09-04 | github-actions[bot] | 1 | +13 / −17 | docs: regenerate the commit log |
| `75daa7c` | 2026-09-04 | heinricitorgau | 31 | +2863 / −230 | Retrain the ML layer on the re-crawled 2026 QS data and the widened pairing |
| `e7a1ae9` | 2026-09-04 | heinricitorgau | 2 | +30 / −2 | Make seed-canonical-from-missing honour its year, and skip non-universities |
| `f74b73d` | 2026-09-04 | heinricitorgau | 3 | +669 / −0 | Add post-ingest verification and a snapshot replay for the ranking year |
| `d87b2ca` | 2026-09-03 | github-actions[bot] | 1 | +12 / −9 | docs: regenerate the commit log |
| `24cf49e` | 2026-09-03 | heinricitorgau | — | — | Merge claude/mapping-review-decided-tab |
| `87259e2` | 2026-09-03 | heinricitorgau | 8 | +371 / −3 | Scope every ranking summary to the world ranking |
| `749e1e0` | 2026-09-02 | github-actions[bot] | 1 | +10 / −7 | docs: regenerate the commit log |
| `7c39325` | 2026-09-02 | heinricitorgau | — | — | Merge origin/main: the commit-log bot's run for the previous push |
| `993ed73` | 2026-09-02 | heinricitorgau | 7 | +435 / −40 | Give the Decided tab a query that can return something |
| `c28472a` | 2026-09-02 | github-actions[bot] | 1 | +21 / −10 | docs: regenerate the commit log |
| `3b8bd39` | 2026-09-02 | heinricitorgau | — | — | Merge origin/main: pick up the bot-regenerated commit log |
| `1338ccf` | 2026-09-02 | heinricitorgau | 1 | +109 / −0 | Fix flaky API Tests CI failure: order-dependent pipeline table check |
| `fe65d0a` | 2026-09-02 | heinricitorgau | 68 | +173148 / −264407 | Re-crawl all 21 QS universes for 2026 |
| `1b5bfe2` | 2026-09-02 | heinricitorgau | 24 | +3821 / −162 | Fix QS crawler: TLS transport, ranking id resolution, admissions concurrency |

## 2026-08

| Commit | 日期 | 作者 | 檔案 | +/− | 說明 |
|---|---|---|---|---|---|
| `8d01ac2` | 2026-08-25 | github-actions[bot] | 1 | +11 / −9 | docs: regenerate the commit log |
| `09b2c0c` | 2026-08-25 | heinricitorgau | 8 | +1419 / −35 | feat(agent): close the loop with conversation history and restore |
| `ea1b634` | 2026-08-25 | github-actions[bot] | 1 | +9 / −7 | docs: regenerate the commit log |
| `249a6ec` | 2026-08-25 | heinricitorgau | 20 | +1909 / −12 | feat(agent): wake the web agent up behind ds4, with a Java-owned save path |
| `3acdcbd` | 2026-08-25 | github-actions[bot] | 1 | +11 / −8 | docs: regenerate the commit log |
| `ce7ba49` | 2026-08-25 | KAO,EN-TSAI | — | — | Merge pull request #22 from heinricitorgau/claude/remove-ranking-records-preview-996301 |
| `3386c7f` | 2026-08-25 | heinricitorgau | 24 | +1468 / −57 | feat(admissions): surface structured entry requirements end to end |
| `4c48513` | 2026-08-25 | github-actions[bot] | 1 | +9 / −7 | docs: regenerate the commit log |
| `48a2382` | 2026-08-25 | KAO,EN-TSAI | — | — | Merge pull request #19 from heinricitorgau/ml/diagnostics-parity |
| `0200f98` | 2026-08-25 | github-actions[bot] | 1 | +20 / −10 | docs: regenerate the commit log |
| `1ba3d96` | 2026-08-25 | KAO,EN-TSAI | — | — | Merge pull request #21 from heinricitorgau/claude/remove-ranking-records-preview-996301 |
| `43217f7` | 2026-08-24 | heinricitorgau | 16 | +209 / −1286 | refactor(warehouse): drop ranking_records_preview end to end |
| `3a16a53` | 2026-08-23 | github-actions[bot] | 1 | +14 / −10 | docs: regenerate the commit log |
| `eef516c` | 2026-08-23 | KAO,EN-TSAI | — | — | Merge pull request #17 from heinricitorgau/feat/admission-ranking-convergence |
| `85c5889` | 2026-08-22 | heinricitorgau | 57 | +3425 / −447 | Converge the admission pipeline onto the ranking entity-resolution stack |
| `92099fa` | 2026-08-22 | heinricitorgau | 5 | +439 / −11 | Cover plot_disagreement_diagnostics.m against sklearn, and fix its binning |
| `1dcd8aa` | 2026-08-22 | github-actions[bot] | 1 | +14 / −11 | docs: regenerate the commit log |
| `aeda786` | 2026-08-22 | KAO,EN-TSAI | — | — | Merge pull request #16 from heinricitorgau/test/inference-batch-invariants |
| `fb4289a` | 2026-08-22 | heinricitorgau | 3 | +214 / −2 | Cover the one MATLAB port parity cannot reach |
| `be32c9d` | 2026-08-21 | github-actions[bot] | 1 | +26 / −8 | docs: regenerate the commit log |
| `3d6c08f` | 2026-08-21 | KAO,EN-TSAI | — | — | Merge pull request #15 from heinricitorgau/fix/entity-resolution-blocking |
| `900c5e9` | 2026-08-21 | heinricitorgau | 2 | +30 / −30 | Retrain the disagreement model on the corrected pairing |
| `a7dc734` | 2026-08-21 | heinricitorgau | 1 | +7 / −7 | Re-run build_cross_source_data.m against the corrected pairing |
| `2c15519` | 2026-08-21 | heinricitorgau | 1 | +77 / −24 | Point the analytics smoke at the path that now exists |
| `4f38d3e` | 2026-08-21 | heinricitorgau | 1 | +29 / −2 | Fold review_queue.sql into mapping_review_queue.sql |
| `17bd1e6` | 2026-08-21 | heinricitorgau | 1 | +6 / −21 | Re-export the pairing after clearing the review backlog |
| `36d587a` | 2026-08-21 | heinricitorgau | 1 | +6 / −1 | Keep the whole note, commas and all |
| `cea607d` | 2026-08-21 | heinricitorgau | 3 | +32 / −7 | Put the decision slot where the eye already is |
| `d79fec7` | 2026-08-21 | heinricitorgau | 1 | +213 / −0 | Make re-exporting the QS-THE pairing a script, not a one-off |
| `bb54267` | 2026-08-21 | heinricitorgau | 3 | +538 / −0 | Add batch tooling for the entity-resolution backlog |
| `290ae7b` | 2026-08-21 | heinricitorgau | 1 | +230 / −15 | Re-export the QS-THE pairing the warehouse now holds |
| `1fdeedd` | 2026-08-21 | heinricitorgau | 3 | +177 / −1 | Take the current rank, not the best one ever recorded |
| `5a3066f` | 2026-08-21 | heinricitorgau | 1 | +2 / −2 | Stop labelling three different stages [4/4] |
| `830234d` | 2026-08-21 | heinricitorgau | 3 | +133 / −16 | Persist the QS profile path instead of dropping it |
| `92a7bf8` | 2026-08-21 | heinricitorgau | 4 | +484 / −165 | Give warehouse.ranking_record one writer |
| `f7c42f8` | 2026-08-21 | heinricitorgau | 1 | +29 / −23 | Let the QS multi-source sync fail loudly |
| `c603d55` | 2026-08-21 | heinricitorgau | 1 | +4 / −1 | Stop pinning the QS run id too |
| `7fb3e23` | 2026-08-21 | github-actions[bot] | 1 | +18 / −9 | docs: regenerate the commit log |
| `608ab2c` | 2026-08-21 | KAO,EN-TSAI | — | — | Merge pull request #14 from heinricitorgau/fix/entity-resolution-blocking |
| `6798057` | 2026-08-21 | heinricitorgau | 1 | +6 / −2 | Stop pinning a constant run id, which made the prune inert |
| `73736db` | 2026-08-21 | heinricitorgau | 1 | +7000 / −1000 | Refresh the ARWU 2026 crawl output |
| `5f89da9` | 2026-08-21 | heinricitorgau | 2 | +184 / −5 | Keep the ARWU source row, in the shape everything downstream expects |
| `e1950cd` | 2026-08-21 | heinricitorgau | 12 | +1255 / −0 | Give the fuzzy-match backlog a review screen |
| `de9e240` | 2026-08-21 | heinricitorgau | 9 | +788 / −0 | Let a reviewer overrule the fuzzy matcher, durably |
| `58ef9fa` | 2026-08-21 | heinricitorgau | 1 | +42 / −42 | Refresh the THE 2026 crawl output |
| `10d184e` | 2026-08-21 | heinricitorgau | 6 | +444 / −28 | Make entity resolution reach the names it was already close to |
| `43bc57c` | 2026-08-20 | github-actions[bot] | 1 | +9 / −7 | docs: regenerate the commit log |
| `246dffa` | 2026-08-20 | heinricitorgau | 1 | +735 / −0 | Add the read-only entity-resolution backlog dry run |
| `4f9c241` | 2026-08-20 | github-actions[bot] | 1 | +8 / −7 | docs: regenerate the commit log |
| `7d87cc5` | 2026-08-20 | heinricitorgau | 3 | +400 / −13 | Regenerate the commit log from CI instead of by hand |
| `3c61988` | 2026-08-20 | KAO,EN-TSAI | — | — | Merge pull request #13 from heinricitorgau/docs/commit-log |
| `ca4ed73` | 2026-08-20 | heinricitorgau | 1 | +29 / −5 | Report the artifact-ordering check instead of enforcing it |
| `50050cf` | 2026-08-20 | heinricitorgau | 3 | +128 / −0 | Make the disagreement inference use the shared cross-source builder |
| `08daf6e` | 2026-08-20 | heinricitorgau | 5 | +226 / −7 | Reproduce the Phase 3 diagnostics figure in MATLAB |
| `5b84ab1` | 2026-08-18 | heinricitorgau | 52 | +9523 / −9492 | Store and check out LF everywhere, and renormalise |
| `dcf06d6` | 2026-08-18 | KAO,EN-TSAI | — | — | Merge pull request #12 from heinricitorgau/docs/commit-log |
| `d3d4991` | 2026-08-18 | heinricitorgau | 13 | +1237 / −241 | Port Phase 3 to MATLAB and generalise the parity guard |
| `5a88eaf` | 2026-08-18 | heinricitorgau | 3 | +364 / −0 | docs: add a generated commit log with per-commit change statistics |
| `449980c` | 2026-08-17 | heinricitorgau | 11 | +446 / −0 | update |
| `170f0e2` | 2026-08-17 | heinricitorgau | 8 | +945 / −55 | Seed 43 more ARWU aliases; ARWU coverage 637 -> 686 |
| `952224a` | 2026-08-17 | heinricitorgau | 5 | +1793 / −197 | Allow $ in minified names; ARWU extraction 897 -> 1000 |
| `339fc69` | 2026-08-17 | heinricitorgau | 2 | +4 / −0 | Link the two READMEs to each other |
| `f54674f` | 2026-08-17 | heinricitorgau | 2 | +79 / −6 | Add contents, prerequisites and a licence section to both READMEs |
| `b13e238` | 2026-08-17 | heinricitorgau | 1 | +111 / −3 | Sync the Chinese README with the English one |
| `232ce5e` | 2026-08-17 | heinricitorgau | 2 | +177 / −2 | Seed 25 reviewed ARWU aliases; three-source coverage 495 -> 508 |
| `58ecdf7` | 2026-08-17 | heinricitorgau | 3 | +341 / −0 | Score the served predictions, not just their shape |
| `6d1293a` | 2026-08-17 | heinricitorgau | 3 | +188 / −0 | Fail loudly when the exported QS-THE pairing goes stale |
| `707329f` | 2026-08-17 | heinricitorgau | 1 | +47 / −6 | Give the idempotency test its own universities |
| `ca254a3` | 2026-08-17 | heinricitorgau | 6 | +338 / −1 | Make source ingestion idempotent |
| `e7820b5` | 2026-08-17 | heinricitorgau | 3 | +14264 / −518 | Read the whole ARWU table from the Nuxt payload, not the 30 rendered rows |
| `6c1692e` | 2026-08-16 | heinricitorgau | 5 | +865 / −13 | Ingest ARWU 2026; 29 universities reach three sources |
| `fb74248` | 2026-08-16 | heinricitorgau | 4 | +63 / −823 | Stop the ARWU crawler labelling old tables with the requested year |
| `b7c6556` | 2026-08-16 | heinricitorgau | 6 | +5542 / −68 | Join QS and THE on the warehouse's reviewed pairing, not a name key |
| `8d88b76` | 2026-08-16 | heinricitorgau | 3 | +844 / −1 | Seed 112 reviewed THE aliases; two-source coverage 969 -> 1080 |
| `0814317` | 2026-08-16 | heinricitorgau | 4 | +212 / −18 | Derive the source-coverage caveats from the warehouse |
| `691ba90` | 2026-08-16 | heinricitorgau | 2 | +49 / −3 | Document what CI actually executes |
| `d2d017e` | 2026-08-16 | heinricitorgau | 4 | +190 / −37 | Re-execute the MATLAB sources in CI now the repository is public |
| `deaf9bf` | 2026-08-16 | heinricitorgau | 6 | +36 / −48 | Drop the skipping API step from smoke_release.sh |
| `69004a6` | 2026-08-16 | heinricitorgau | 3 | +80 / −34 | Run the API endpoint checks in CI instead of skipping them |
| `b3aef36` | 2026-08-16 | heinricitorgau | 2 | +157 / −0 | Run smoke_analytics_bridge in CI against a live API |
| `7f17082` | 2026-08-16 | heinricitorgau | 2 | +88 / −7 | Run the opt-in PostgreSQL tests in CI |
| `76cab93` | 2026-08-16 | heinricitorgau | 2 | +157 / −0 | Cover the superseded-row prune with a regression test |
| `5f793b5` | 2026-08-16 | heinricitorgau | 1 | +65 / −0 | Prune superseded rows from analytics.aggregated_rankings |
| `af3f033` | 2026-08-15 | heinricitorgau | 11 | +183 / −35 | Set source weights to QS 0.222 / THE 0.654 / ARWU 0.124 |
| `98619fc` | 2026-08-15 | heinricitorgau | 3 | +314 / −36 | Catch faith-108: ordering claims over dimensions the evidence lacks |
| `432c608` | 2026-08-15 | heinricitorgau | 8 | +548 / −41 | Add a structured provenance signal to explanation verification |
| `4f16aab` | 2026-08-15 | heinricitorgau | 3 | +265 / −20 | eval(agent): nine more cases beyond the rules, and what the judge misses has a shape |
| `cd95973` | 2026-08-15 | heinricitorgau | 4 | +143 / −18 | fix(agent): the dark-judge warning was going to the wrong stream, and the recovery never appeared |
| `10e1539` | 2026-08-15 | heinricitorgau | 3 | +117 / −4 | feat(agent): make a judge that has gone dark say so |
| `5a65e8b` | 2026-08-15 | heinricitorgau | 4 | +204 / −5 | feat(agent): serve the verification counters at GET /api/v1/agent/stats |
| `a495284` | 2026-08-15 | heinricitorgau | 3 | +118 / −4 | feat(agent): count verification outcomes, and say what still is not watched |
| `7ba7736` | 2026-08-15 | heinricitorgau | 19 | +539 / −52 | feat(agent): verify explanations at generation time, with the judge as second signal |
| `bc635f6` | 2026-08-15 | heinricitorgau | 5 | +437 / −36 | eval(agent): add cases the rules cannot express, which reverses the judge verdict |
| `f618502` | 2026-08-15 | heinricitorgau | 2 | +34 / −2 | fix(ml): the MATLAB freshness guard could never fire in CI |
| `67eefc3` | 2026-08-15 | heinricitorgau | 3 | +117 / −16 | test(ml): guard the MATLAB artifacts against going stale |
| `18d5999` | 2026-08-15 | heinricitorgau | 7 | +500 / −4 | ci(ml): exercise the serving write path, and fix the bug that found |
| `36beb97` | 2026-08-15 | heinricitorgau | 9 | +475 / −9 | feat(ml): serve the disagreement probability, and stop the two targets mixing |
| `2874e64` | 2026-08-15 | heinricitorgau | 4 | +600 / −3 | eval(agent): measure an LLM judge against the rule checker, and reject it |
| `d292984` | 2026-08-15 | heinricitorgau | 2 | +58 / −1 | fix(tests): un-rot a cache fixture, and run this suite in CI so it cannot rot again |
| `a05ff8a` | 2026-08-15 | heinricitorgau | 4 | +1479 / −1355 | refactor(pipeline): move the canonical and source-ingestion commands out |
| `a23e94b` | 2026-08-15 | heinricitorgau | 2 | +71 / −33 | refactor(pipeline): share the PostgreSQL helpers, unblocking the last group |
| `e28859f` | 2026-08-15 | heinricitorgau | 4 | +814 / −750 | refactor(pipeline): move the ranking commands into pipeline/commands/ |
| `ab99047` | 2026-08-15 | heinricitorgau | 2 | +165 / −2 | fix(pipeline): repair two NameErrors, and add the check that found them |
| `924febc` | 2026-08-15 | heinricitorgau | 3 | +588 / −544 | refactor(pipeline): move the admission commands into pipeline/commands/ |
| `dde37a6` | 2026-08-12 | heinricitorgau | 1 | +911 / −806 | refactor(pipeline): replace the 900-line dispatch ladder with a command registry |
| `ab122cf` | 2026-08-12 | heinricitorgau | 1 | +68 / −0 | tooling: add a CLI-surface snapshot for refactoring run_pipeline.py |
| `9af329d` | 2026-08-12 | heinricitorgau | 3 | +17 / −0 | docs: show the running application in the README |
| `d027bce` | 2026-08-12 | heinricitorgau | 8 | +250 / −16 | test(ml): verify the MATLAB EDA port against the Python one |
| `56d0380` | 2026-08-12 | heinricitorgau | 5 | +558 / −4 | ci: guard the modelling layer with feature tests and a metrics gate |
| `1238178` | 2026-08-09 | heinricitorgau | 12 | +743 / −12 | feat(ml): store estimates in analytics.ml_predictions and serve them |
| `07901c4` | 2026-08-09 | heinricitorgau | 11 | +717 / −0 | Add MATLAB port of the QS indicator EDA |
| `8e18beb` | 2026-08-09 | heinricitorgau | 6 | +134 / −4 | fix: correct subject rankings assertion and make API tests DB-independent |
| `1900f04` | 2026-08-09 | heinricitorgau | 4 | +163 / −6 | feat(api): add the model-estimate caveat to the analytics honesty contract |
| `2800602` | 2026-08-09 | heinricitorgau | 8 | +1122 / −13 | feat(ml): add the cross-source disagreement classifier and score the faithfulness checker |
| `8a10e05` | 2026-08-09 | heinricitorgau | 12 | +1062 / −10 | feat(ml): train and evaluate the QS overall-score estimator |
| `9118c94` | 2026-08-09 | heinricitorgau | 14 | +957 / −0 | feat(ml): add the modelling layer's feature contract and EDA |
| `7f3664f` | 2026-08-08 | heinricitorgau | 11 | +642 / −24 | feat(agent): comparison and application-plan explanation surfaces |
| `7c4b106` | 2026-08-08 | heinricitorgau | 340 | +25 / −98562 | chore: remove vendored mini-agent and generated lobster-01 runtime copy |
| `76340bb` | 2026-08-08 | heinricitorgau | 2 | +25 / −4 | feat: trim the downloadable source archive to a runnable package |
| `7f45cde` | 2026-08-08 | heinricitorgau | 10 | +659 / −3 | feat: surface ds4 explanations on the recommendations page |
| `5edd128` | 2026-08-08 | heinricitorgau | 3 | +224 / −2 | feat(agent): SSE streaming transport for ds4 generation |
| `4a00860` | 2026-08-08 | heinricitorgau | 6 | +629 / −7 | feat(autoeval): mechanical faithfulness eval for generated explanations |
| `cf93e35` | 2026-08-08 | heinricitorgau | 4 | +153 / −9 | feat(agent): configurable ds4 timeout and generation observability |

## 2026-07

| Commit | 日期 | 作者 | 檔案 | +/− | 說明 |
|---|---|---|---|---|---|
| `1af6acc` | 2026-07-23 | heinricitorgau | 1 | +4 / −0 | docs: add CI badges to README.zh-TW.md |
| `c560d80` | 2026-07-23 | heinricitorgau | 1 | +11 / −0 | docs(ds4): show CI status in the tests section |
| `050486d` | 2026-07-23 | heinricitorgau | 1 | +2 / −0 | docs: add Data Quality and Release Smoke CI badges to README |
| `e6dab02` | 2026-07-23 | heinricitorgau | 1 | +2 / −0 | docs: add Agent Tests CI badge to README |
| `35b5362` | 2026-07-23 | heinricitorgau | 1 | +45 / −0 | ci: run ds4 / web-agent generation tests on push and PR |
| `20bfb7e` | 2026-07-23 | heinricitorgau | 2 | +174 / −3 | test(agent): add mock-server live-path integration test for ds4 |
| `8a781e7` | 2026-07-23 | heinricitorgau | 1 | +1 / −1 | docs: note remote ds4-server setup in the README doc link |
| `39590b5` | 2026-07-23 | heinricitorgau | 1 | +55 / −0 | docs(ds4): document pointing CrawlerNest at a remote ds4-server |
| `2cde8a3` | 2026-07-23 | heinricitorgau | 4 | +684 / −346 | refactor(agent): split context-builder god method and table-drive prompt builder |
| `e1ca8a9` | 2026-07-22 | heinricitorgau | 10 | +248 / −292 | refactor(agent): dedup the web-agent generation layer (simplify sweep) |
| `2660932` | 2026-07-22 | heinricitorgau | 5 | +184 / −220 | refactor(agent): extract shared GroundedExplainer base for the ds4 explainers |
| `c7f8158` | 2026-07-22 | heinricitorgau | 8 | +621 / −12 | feat(agent): add ds4 explainers for university_lookup and data_query |
| `db60854` | 2026-07-22 | heinricitorgau | 7 | +336 / −7 | feat(agent): add ds4 ranking-explain explanation generator |
| `f9877c6` | 2026-07-22 | heinricitorgau | 3 | +43 / −0 | feat(agent): wire ds4 recommendation explainer into the live web-agent path |
| `85899d9` | 2026-07-22 | heinricitorgau | 4 | +500 / −0 | feat(agent): add ds4 local-model provider and recommendation explainer |
| `d2296ec` | 2026-07-14 | heinricitorgau | 1 | +89 / −26 | docs: expand landing page with Why CrawlerNest and design principles |
| `f642a96` | 2026-07-14 | heinricitorgau | 2 | +140 / −0 | feat: add GitHub Pages landing page with download links |
| `7229ded` | 2026-07-14 | heinricitorgau | 3 | +222 / −3 | feat: add one-command first-time setup for self-hosted data |
| `d76e99a` | 2026-07-14 | heinricitorgau | 1 | +22 / −0 | feat(web): harden robots.txt against crawler overload |
| `a965936` | 2026-07-14 | heinricitorgau | 1 | +2 / −5 | feat(web): add crawl-delay and query-string disallow to robots.txt |
| `585211d` | 2026-07-14 | heinricitorgau | 1 | +14 / −0 | feat(web): add robots.txt excluding API routes and user pages |
| `0ffc9cc` | 2026-07-14 | heinricitorgau | 1 | +4 / −1 | fix(web): allow dev access from WSL NAT IP via allowedDevOrigins |
| `6ceb3d2` | 2026-07-06 | heinricitorgau | 99 | +17 / −278 | chore: untrack build artifacts and deprecated ranking-crawler copy |
| `bce364c` | 2026-07-04 | heinricitorgau | 4 | +136 / −10 | fix: correct source count in analytics trends; add banner anchor links and root CLAUDE.md |
| `9234990` | 2026-07-04 | heinricitorgau | 3 | +356 / −1136 | docs: rewrite READMEs as project overview, extract setup to GETTING_STARTED.md |
| `2769920` | 2026-07-04 | heinricitorgau | 102 | +41 / −42 | refactor: move crawlernest-agents and C engine into crawlernest/ module tree |
| `9a578d5` | 2026-07-04 | heinricitorgau | 45 | +7 / −244 | chore: clean up repo root — untrack runtime artifacts, consolidate samples, move tests |
| `e80265a` | 2026-07-04 | heinricitorgau | 51 | +15 / −4404 | refactor: consolidate C normalization engine into Clawer-C-Data-Normalization-Engine |
| `805ea5a` | 2026-07-04 | heinricitorgau | 96 | +11502 / −9 | chore: add Clawer-C-Data-Normalization-Engine and crawlernest-agents, update docs |

## 2026-06

| Commit | 日期 | 作者 | 檔案 | +/− | 說明 |
|---|---|---|---|---|---|
| `3654ac8` | 2026-06-12 | heinricitorgau | 6 | +97 / −11 | feat: add business-management subject rankings ingestion and cookie consent banner |
| `108f7ea` | 2026-06-12 | heinricitorgau | 98 | +261 / −261 | refactor(docs): reorganize flat docs/ into 7 subdirectories with corrected cross-references |
| `8d668d8` | 2026-06-09 | heinricitorgau | 6 | +941 / −0 | docs: add Phase 4 competition demo rehearsal — judge simulation, narrative audit, timing scripts, screenshot priorities, agent value assessment, and readiness scorecard |
| `2b0457a` | 2026-06-06 | heinricitorgau | 9 | +379 / −0 | docs: prepare readonly agent for competition demo |
| `7c6b2fd` | 2026-06-06 | heinricitorgau | 5 | +270 / −27 | feat: align agent responses with readonly system prompt |
| `1f34d8a` | 2026-06-06 | heinricitorgau | 34 | +5002 / −136 | feat: add readonly agent model provider bridge |

## 2026-05

| Commit | 日期 | 作者 | 檔案 | +/− | 說明 |
|---|---|---|---|---|---|
| `f9d5299` | 2026-05-24 | heinricitorgau | 1 | +3 / −3 | test: align maintenance phase 6 validation with overview steps |
| `45abbc7` | 2026-05-23 | heinricitorgau | 1 | +63 / −0 | add cross-repo AI debug review wrapper |
| `92266f4` | 2026-05-23 | heinricitorgau | 54 | +6521 / −85 | feat: add explainable analytics and recommendation evidence |
| `06ec731` | 2026-05-23 | heinricitorgau | 58 | +7268 / −41 | feat: add competition analytics prototype |
| `c42f2f8` | 2026-05-16 | heinricitorgau | 80 | +1736 / −339 | chore: stabilize auth UX and prepare RC-1 operational freeze documentation |
| `e6bee26` | 2026-05-16 | heinricitorgau | 4 | +208 / −8 | chore: harden user data safety review and validation |
| `8ea3404` | 2026-05-16 | heinricitorgau | 15 | +942 / −1 | feat: add saved recommendation plans for signed-in users |
| `9fce0eb` | 2026-05-16 | heinricitorgau | 42 | +1735 / −36 | feat: add saved universities for signed-in users |
| `caa34bf` | 2026-05-16 | heinricitorgau | 20 | +3388 / −0 | docs: package v0.1 demo release milestone **[tag: v0.1-demo]** |
| `c03ecb6` | 2026-05-09 | heinricitorgau | 1 | +10 / −1 | update whitepaper |
| `181d977` | 2026-05-09 | heinricitorgau | 29 | +757 / −529 | update architecture pic |
| `7b6279f` | 2026-05-09 | heinricitorgau | 18 | +1113 / −21 | chore: reduce operational risk with env, backup, and fixture checks |
| `c3e59b9` | 2026-05-08 | heinricitorgau | 5 | +466 / −2 | docs: add full project state review |
| `362423c` | 2026-05-08 | heinricitorgau | 6 | +856 / −8 | chore: add operational reliability checks and cleanup tooling |
| `f61bd12` | 2026-05-08 | heinricitorgau | 7 | +645 / −0 | chore: add readonly repo-aware agent context snapshots |
| `a0eb90b` | 2026-05-08 | heinricitorgau | 12 | +887 / −710 | chore: add readonly crawlernest-agents debug wrapper |
| `28a1b87` | 2026-05-08 | heinricitorgau | 12 | +1243 / −67 | docs: sync architecture and operational documentation |
| `0bdeeab` | 2026-05-08 | heinricitorgau | 10 | +1170 / −5 | feat: add cross-source ranking intelligence and explainability |
| `4a99140` | 2026-05-08 | heinricitorgau | 9 | +516 / −9 | ci: add continuous verification workflows and fixture-based regression checks |
| `91a9c1a` | 2026-05-08 | heinricitorgau | 24 | +3360 / −32 | feat: add operational automation and system snapshots |
| `67f0e7e` | 2026-05-08 | heinricitorgau | 5 | +721 / −0 | docs: add demo checklist and local troubleshooting guide |
| `ede8116` | 2026-05-08 | heinricitorgau | 20 | +1728 / −26 | feat: add freshness checks and incremental ingestion guards |
| `e8ed031` | 2026-05-08 | heinricitorgau | 27 | +1128 / −988 | feat(local-stack): stabilize WSL localhost pipeline, PostgreSQL integration, and rankings API startup |

## 2026-04

| Commit | 日期 | 作者 | 檔案 | +/− | 說明 |
|---|---|---|---|---|---|
| `16a3841` | 2026-04-29 | Heinrici Torgau | 50 | +4349 / −684 | feat: add subject rankings pipeline, API, web UI, and bootstrap support |
| `9130862` | 2026-04-28 | Heinrici Torgau | 6 | +231 / −17 | fix(agent): extract country from prompt in RankingTools |
| `102a9dc` | 2026-04-28 | Heinrici Torgau | 13 | +2459 / −2382 | update |
| `fda9ba0` | 2026-04-28 | Heinrici Torgau | 1 | +29 / −0 | reflesh scripts/start_localhost.sh |
| `bbfa852` | 2026-04-28 | Heinrici Torgau | 3 | +35 / −6 | add scripts/start_localhost.sh |
| `83c08e3` | 2026-04-26 | Heinrici Torgau | 1 | +2 / −1 | update whitepaper |
| `f1d507a` | 2026-04-26 | Heinrici Torgau | 29 | +1312 / −496 | 2026-04-26 - Added analytics bridge for legacy QS rankings. - Seeded ranking_source and canonical_university automatically. - Synced warehouse.rankings into warehouse.ranking_record. - Added aggregation run and populated analytics.aggregated_rankings. - Fixed duplicate legacy ranking rows using DISTINCT ON before ON CONFLICT. - Verified /api/v1/rankings returns 1499 total records. |
| `70e3894` | 2026-04-24 | Heinrici Torgau | 5 | +29 / −0 | update readme and whitepaper |
| `2333ef2` | 2026-04-24 | Heinrici Torgau | 15 | +2366 / −877 | update readme and whitepaper |
| `c8d2f39` | 2026-04-24 | Heinrici Torgau | 4 | +312 / −40 | docs: productize README with system flow, demo script, and clear decision-support positioning |
| `d99a881` | 2026-04-24 | Heinrici Torgau | 8 | +3239 / −45 | feat: add deterministic decision summary export with readable text format and clipboard support |
| `4514b54` | 2026-04-23 | Heinrici Torgau | 5 | +1725 / −17 | Add deterministic multi-scenario comparison layer to identify highest-impact profile improvements without altering core recommendation logic. |
| `bb6607b` | 2026-04-22 | Heinrici Torgau | 6 | +1581 / −3 | add application plan comparison matrix |
| `ce6c0e4` | 2026-04-22 | Heinrici Torgau | 17 | +506 / −27 | docs(architecture): define shared crawler-core boundary |
| `e9f73af` | 2026-04-22 | Heinrici Torgau | 21 | +3314 / −69 | feat(recommendation): introduce structured decision, concern, and surface-priority layers |
| `12454bd` | 2026-04-19 | Heinrici Torgau | 7 | +11 / −16 | chore: remove lobster compatibility shim |
| `372479a` | 2026-04-19 | Heinrici Torgau | 3 | +143 / −4 | chore: remove top-level scripts compatibility shim |
| `2d550e0` | 2026-04-19 | Heinrici Torgau | 6 | +0 / −6 | chore: remove legacy top-level compatibility symlinks |
| `4dfc06c` | 2026-04-19 | Heinrici Torgau | 3 | +0 / −3 | docs: remove redundant docs root entries |
| `7ee2635` | 2026-04-19 | Heinrici Torgau | 2 | +0 / −0 | update /docs file |
| `1376385` | 2026-04-19 | Heinrici Torgau | 18 | +358 / −507 | update /docs file |
| `1c3f243` | 2026-04-19 | Heinrici Torgau | 175 | +19160 / −74 | update .md file |
| `a454939` | 2026-04-18 | Heinrici Torgau | 54 | +5465 / −337 | docs: translate system architecture docs to English and add regression-safe pipeline & eval loop sectio |
| `b5c1f4e` | 2026-04-18 | Heinrici Torgau | 9 | +223 / −613 | update .md file |
| `c5eb8d7` | 2026-04-18 | Heinrici Torgau | 6 | +645 / −0 | update system engine structure |
| `41c9c67` | 2026-04-18 | Heinrici Torgau | 3 | +45 / −17 | update system structure |
| `bbb1831` | 2026-04-18 | Heinrici Torgau | 1 | +10 / −84 | update system engine structure |
| `45538dd` | 2026-04-18 | Heinrici Torgau | 11 | +725 / −244 | update system engine structure |
| `a1ccb05` | 2026-04-18 | Heinrici Torgau | 48 | +5453 / −399 | update structure |
| `026d720` | 2026-04-17 | Heinrici Torgau | 135 | +11124 / −2899 | feat: ship product-facing rankings and generative web agent foundation |
| `01ac004` | 2026-04-15 | Heinrici Torgau | 16 | +422 / −801 | feat(preview-pipeline): add rebuild-preview-and-resolve orchestration command |
| `4bae59c` | 2026-04-15 | Heinrici Torgau | 16 | +1148 / −0 | feat(university-preview-api): add thin canonical university detail preview endpoint |
| `5043ae0` | 2026-04-15 | Heinrici Torgau | 4 | +576 / −0 | feat(detail-preview): add canonical university detail preview from shared identity and preview tables |
| `cace412` | 2026-04-15 | Heinrici Torgau | 2 | +54 / −21 | feat(convergence-preview): validate ranking and admission convergence on shared canonical identity |
| `99d1685` | 2026-04-15 | Heinrici Torgau | 3 | +359 / −0 | feat(convergence-preview): add ranking-admission convergence preview on shared canonical identity |
| `48b298e` | 2026-04-14 | Heinrici Torgau | 4 | +188 / −19 | feat(admission-resolution): add deterministic entity resolution and unresolved reporting |
| `34eca7d` | 2026-04-14 | Heinrici Torgau | 19 | +1776 / −15 | feat(admission-pipeline): add first-pass admission staging and warehouse preview flow |
| `a0ac18b` | 2026-04-13 | Heinrici Torgau | 23 | +1286 / −41 | refactor(ranking-api): make decision table the single source of truth for ranking read path |
| `6145040` | 2026-04-13 | Heinrici Torgau | 6 | +76 / −143 | update timeline |
| `22088f2` | 2026-04-13 | Heinrici Torgau | 2 | +99 / −41 | update structure pic |
| `7899643` | 2026-04-12 | Heinrici Torgau | 1 | +97 / −97 | update .md file |
| `b8bfb3f` | 2026-04-12 | Heinrici Torgau | 12 | +469 / −138 | update .md file |
| `7eb6298` | 2026-04-12 | Heinrici Torgau | 7 | +552 / −5 | feat(ranking-resolution): add unresolved reporting and manual alias seeding workflow |
| `a268682` | 2026-04-12 | Heinrici Torgau | 3 | +223 / −0 | feat(ranking-pipeline): add deterministic entity resolution for warehouse preview rows |
| `7bce873` | 2026-04-12 | Heinrici Torgau | 3 | +34 / −14 | fix(ranking-pipeline): align PostgreSQL driver loading across staging ingest and warehouse landing writes |
| `0f0dc94` | 2026-04-12 | Heinrici Torgau | 3 | +340 / −0 | feat(ranking-pipeline): add warehouse preview mapper for staging-to-warehouse contract |
| `1ee7261` | 2026-04-12 | Heinrici Torgau | 4 | +280 / −0 | feat(ranking-pipeline): enable real PostgreSQL staging ingestion via write adapter |
| `a97b565` | 2026-04-12 | Heinrici Torgau | 5 | +144 / −36 | feat(ranking-pipeline): add PostgreSQL staging write adapter for target-agnostic ingest |
| `6a4ccea` | 2026-04-12 | Heinrici Torgau | 6 | +218 / −67 | feat(ranking-pipeline): add staging ingest layer with SQLite persistence |
| `9807668` | 2026-04-12 | Heinrici Torgau | 6 | +244 / −19 | feat(ranking-pipeline): add staging validation gate before ingest |
| `2fde582` | 2026-04-12 | Heinrici Torgau | 27 | +706 / −0 | feat(ranking-pipeline): add staging JSONL writer and extend crawl-ranking data flow |
| `d5eb96a` | 2026-04-12 | Heinrici Torgau | 2 | +385 / −360 | rewrite repo structure and write system/engine structure |
| `9e7c716` | 2026-04-12 | Heinrici Torgau | 11 | +194 / −47 | def initial crawler engine into ranking/admission crawler |
| `c7fb963` | 2026-04-12 | Heinrici Torgau | 16 | +557 / −0 | def initial crawler engine into ranking/admission crawler |
| `37cc438` | 2026-04-12 | Heinrici Torgau | 1 | +339 / −184 | draw system structure pic into REPO_STRUCTURE.md |
| `63ef2dc` | 2026-04-12 | Heinrici Torgau | 1 | +211 / −107 | draw structure into REPO_STRUCTURE.md |
| `40b5175` | 2026-04-11 | Heinrici Torgau | 9 | +1 / −3537 | delet crawlernest/crawlernest-autoeval/sandbox/autoloop/prompts/iter_001.prompt.md crawlernest/crawlernest-autoeval/sandbox/autoloop/prompts/iter_002.prompt.md crawlernest/crawlernest-autoeval/sandbox/autoloop/prompts/iter_003.prompt.md crawlernest/crawlernest-autoeval/sandbox/autoloop/prompts/iter_004.prompt.md crawlernest/crawlernest-autoeval/sandbox/autoloop/prompts/iter_005.prompt.md docs/foundation/SESSION_REPORT_2026_04_02.md docs/foundation/progress_report_20260401.md docs/archive/POSTGRES_MIGRATION_HISTORY.md |
| `04abf72` | 2026-04-11 | Heinrici Torgau | 4 | +155 / −380 | delet crawlernest/crawlernest-mini-agent/rust/USAGE.md crawlernest/crawlernest-mini-agent/rust/PARITY.md crawlernest/crawlernest-mini-agent/rust/.omc/plans/tui-enhancement-plan.md |
| `d06ac84` | 2026-04-10 | Heinrici Torgau | 21 | +2111 / −196 | feat(agent): add evaluation-driven dev-agent loop with validation pipeline and initial file-aware scaffolding |
| `a84dc1a` | 2026-04-10 | Heinrici Torgau | 1 | +1 / −0 | add ./mvnw clean in readme |
| `173163b` | 2026-04-10 | Heinrici Torgau | 1 | +1 / −0 | add ./mvnw clean in readme |
| `2cf44e6` | 2026-04-10 | Heinrici Torgau | 2 | +0 / −2 | delet repeat in readme |
| `22feb16` | 2026-04-10 | Heinrici Torgau | 13 | +534 / −0 | record detial for autoeval |
| `fd87e59` | 2026-04-08 | Heinrici Torgau | 472 | +81728 / −37996 | change file |
| `179968e` | 2026-04-08 | Heinrici Torgau | 1 | +0 / −0 | rename |
| `d933610` | 2026-04-08 | Heinrici Torgau | 6 | +214 / −600 | delet repeat file and match chinese readme with english and rename license |
| `83ce9c0` | 2026-04-08 | Heinrici Torgau | 1 | +7 / −24 | update timeline in whitepaper |
| `19e50ab` | 2026-04-08 | Heinrici Torgau | 1 | +40 / −6 | update whitepaper |
| `206fbe1` | 2026-04-08 | Heinrici Torgau | 2 | +120 / −4 | update readme and whitepaper |
| `1ee5cf0` | 2026-04-08 | Heinrici Torgau | 1 | +1 / −0 | add mini agent |
| `441b814` | 2026-04-08 | Heinrici Torgau | 4 | +0 / −947 | del repeat |
| `41693b2` | 2026-04-08 | Heinrici Torgau | 237 | +40289 / −67 | add lobster file |
| `50bea92` | 2026-04-06 | Heinrici Torgau | 18 | +1293 / −1274 | update struct |
| `d090a78` | 2026-04-06 | Heinrici Torgau | 1 | +302 / −0 | update |
| `a070e2e` | 2026-04-06 | Heinrici Torgau | 3 | +45 / −3 | update readme whitepaper |
| `3a8662a` | 2026-04-05 | Heinrici Torgau | 25 | +673 / −166 | feat(country-normalization): introduce canonical country handling and fix inconsistent filtering across variants |
| `f1ae58b` | 2026-04-05 | Heinrici Torgau | 2 | +74 / −66 | Refactor RankingService and JdbcScopedRankingReadAdapter for improved country handling |
| `199664a` | 2026-04-05 | Heinrici Torgau | 3 | +77 / −65 | Refactor JdbcScopedRankingReadAdapter to streamline SQL query construction |
| `5ec7cac` | 2026-04-05 | Heinrici Torgau | 134 | +2247 / −1271 | Refactor JdbcScopedRankingReadAdapter to improve country filtering functionality |
| `6f0a1b9` | 2026-04-05 | Heinrici Torgau | 1 | +131 / −63 | Enhance JdbcScopedRankingReadAdapter to support country filtering |
| `4b9cf81` | 2026-04-03 | Heinrici Torgau | 92 | +2441 / −1961 | update fronted |
| `e2bbfcb` | 2026-04-03 | KAO,EN-TSAI | — | — | Merge pull request #11 from heinricitorgau/feat/normalization-bridge |
| `31d9557` | 2026-04-03 | Heinrici Torgau | 14 | +652 / −99 | Refine ranking aggregation truth and ranking presentation |
| `73d54c3` | 2026-04-03 | KAO,EN-TSAI | — | — | Merge pull request #10 from heinricitorgau/feat/normalization-bridge |
| `f0d1ad5` | 2026-04-03 | Heinrici Torgau | 1 | +162 / −2 | Enhance UniversityService to support fallback retrieval of university data |
| `a1110e3` | 2026-04-03 | KAO,EN-TSAI | — | — | Merge pull request #9 from heinricitorgau/feat/normalization-bridge |
| `67e2b64` | 2026-04-03 | Heinrici Torgau | 11 | +828 / −2001 | Remove unused pipeline checkpoint journal file and update compiled Python files for config and fetcher modules. |
| `4284977` | 2026-04-03 | Heinrici Torgau | 3 | +42 / −4 | Add ARWU world rankings ingestion to run_production_safe.sh |
| `adfc6c8` | 2026-04-03 | KAO,EN-TSAI | — | — | Merge pull request #8 from heinricitorgau/feat/normalization-bridge |
| `c5e46de` | 2026-04-03 | Heinrici Torgau | 2 | +82 / −12 | Update README files to enhance THE rankings ingestion documentation |
| `084834f` | 2026-04-03 | KAO,EN-TSAI | — | — | Merge pull request #7 from heinricitorgau/feat/normalization-bridge |
| `3eb8a95` | 2026-04-03 | Heinrici Torgau | 30 | +1002 / −70 | Implement THE rankings ingestion and related enhancements |
| `d48d123` | 2026-04-03 | Heinrici Torgau | 4 | +1197 / −0 | Update compiled Python bytecode files in the __pycache__ directories for run_pipeline, config, and fetcher modules. |
| `873768d` | 2026-04-03 | Heinrici Torgau | 4 | +344 / −146 | Refactor error handling and user agent configuration in CrawlerNest |
| `5f0f7c7` | 2026-04-03 | Heinrici Torgau | 71 | +1928 / −26687 | Enhance run_production_safe.sh and run_pipeline.py for improved error handling and timestamp formatting |
| `e0ca080` | 2026-04-03 | Heinrici Torgau | 2 | +591 / −106 | update |
| `1cd9e43` | 2026-04-03 | Heinrici Torgau | 3 | +470 / −10 | fff |
| `a2f1d0c` | 2026-04-03 | KAO,EN-TSAI | — | — | Merge pull request #3 from heinricitorgau/claude/infallible-chatterjee |
| `48ae054` | 2026-04-03 | KAO,EN-TSAI | — | — | Merge branch 'main' into claude/infallible-chatterjee |
| `82b323a` | 2026-04-03 | KAO,EN-TSAI | — | — | Merge pull request #6 from heinricitorgau/feat/normalization-bridge |
| `e787cbd` | 2026-04-03 | KAO,EN-TSAI | — | — | Merge pull request #5 from heinricitorgau/claude/pensive-goldwasser |
| `da984d7` | 2026-04-03 | Heinrici Torgau | 5 | +37 / −3 | feat(web): Phase 2 UX polish — metadata, rank format, page titles |
| `eb0ce37` | 2026-04-03 | KAO,EN-TSAI | — | — | Merge pull request #4 from heinricitorgau/claude/loving-swirles |
| `f8a60c4` | 2026-04-03 | Heinrici Torgau | 1 | +1 / −1 | fix: resolve country filter causing 500 error in recommendations endpoint |
| `a7c68f5` | 2026-04-02 | Heinrici Torgau | 6 | +973 / −15 | feat: enhance C normalizer engine + Python subprocess bridge |
| `61734c8` | 2026-04-02 | KAO,EN-TSAI | — | — | Merge pull request #2 from heinricitorgau/feat/normalization-bridge |
| `6ac9910` | 2026-04-02 | Heinrici Torgau | 10 | +571 / −56 | feat: CrawlerNest full maintenance session 2026-04-02 |
| `b7f0f8b` | 2026-04-02 | Heinrici Torgau | 1 | +5 / −2 | chore: ignore local tool and build artifacts |
| `d658724` | 2026-04-02 | Heinrici Torgau | 5 | +338 / −54 | feat: add pageSize support and normalization bridge |
| `8a05e7b` | 2026-04-02 | Heinrici Torgau | 5 | +1 / −4 | remove claude worktrees from repository |
| `91ab0c6` | 2026-04-02 | Heinrici Torgau | 2 | +143 / −0 | merge claude |
| `cd95e2a` | 2026-04-01 | Heinrici Torgau | 7 | +63 / −447 | update |
| `2784c13` | 2026-04-01 | Heinrici Torgau | 3 | +0 / −3 | remove embedded git repo (.claude) |
| `070f1c3` | 2026-04-01 | Heinrici Torgau | — | — | merge claude branch |
| `ae41613` | 2026-04-01 | Heinrici Torgau | 84 | +158411 / −12270 | cloude help |
| `22e4a09` | 2026-04-01 | Heinrici Torgau | 14 | +7567 / −2584 | feat: Skeleton Loading, ErrorBanner, Jest setup, 51 frontend tests (2026-04-01 PM) |

## 2026-03

| Commit | 日期 | 作者 | 檔案 | +/− | 說明 |
|---|---|---|---|---|---|
| `cbf998f` | 2026-03-30 | Heinrici Torgau | 6 | +502 / −103 | update many |
| `dd07319` | 2026-03-30 | Heinrici Torgau | 25 | +384 / −41934 | update gitignore |
| `8ca5eed` | 2026-03-30 | Heinrici Torgau | 1 | +1 / −1 | update readme |
| `eb3e033` | 2026-03-30 | Heinrici Torgau | 7 | +11 / −79617 | update readme |
| `854a510` | 2026-03-30 | Heinrici Torgau | 23 | +5680 / −65 | update readme |
| `b900b94` | 2026-03-30 | Heinrici Torgau | 92 | +103320 / −31732 | update |
| `19c4cc7` | 2026-03-29 | Heinrici Torgau | 26 | +231116 / −58 | uodate |
| `e994898` | 2026-03-29 | Heinrici Torgau | 91 | +198470 / −64 | fix the front problem |
| `3c31fec` | 2026-03-29 | Heinrici Torgau | 9 | +191 / −97 | update license |
| `75e50b9` | 2026-03-29 | Heinrici Torgau | 17 | +96 / −10625 | update |
| `36dc2e8` | 2026-03-28 | Heinrici Torgau | 41 | +1012 / −16278 | update crawlernest-engine |
| `4ac4927` | 2026-03-27 | Heinrici Torgau | 3 | +54 / −0 | update readme |
| `5d3ee1b` | 2026-03-27 | Heinrici Torgau | 2 | +765 / −833 | update whitepaper |
| `5a206ca` | 2026-03-27 | Heinrici Torgau | 210 | +65451 / −1334 | big update |
| `1b90781` | 2026-03-26 | Heinrici Torgau | 155 | +14348 / −4342 | update |
| `5c98813` | 2026-03-24 | Heinrici Torgau | 55 | +1623 / −1461 | update recommend-v3 |
| `3c2eff2` | 2026-03-23 | Heinrici Torgau | 4 | +561 / −56 | update |
| `728de2a` | 2026-03-23 | Heinrici Torgau | 137 | +7080 / −537 | update |
| `b2f19cb` | 2026-03-23 | Heinrici Torgau | 8 | +273 / −11 | up |
| `e034a7b` | 2026-03-23 | Heinrici Torgau | 143 | +4312 / −377 | add function |
| `0772307` | 2026-03-23 | Heinrici Torgau | 18 | +709 / −0 | add Entity Resolution System |
| `1edd8d7` | 2026-03-23 | Heinrici Torgau | 11 | +500 / −33 | f |
| `ddf2b14` | 2026-03-23 | Heinrici Torgau | 3 | +23 / −0 | update readme whitepaper test-guide |
| `5e322db` | 2026-03-23 | Heinrici Torgau | 24 | +837 / −121 | add speed |
| `7771201` | 2026-03-22 | Heinrici Torgau | 57 | +2407 / −3247 | update all |
| `f1f46c1` | 2026-03-22 | Heinrici Torgau | 18 | +5500 / −896 | update |
| `3f7f5f4` | 2026-03-22 | Heinrici Torgau | 36 | +6631 / −3496 | update auroeval |
| `dd896ba` | 2026-03-22 | Heinrici Torgau | 2 | +11 / −1 | add function |
| `b6e281f` | 2026-03-22 | Heinrici Torgau | 3 | +378 / −125 | mess |
| `985d8c6` | 2026-03-22 | Heinrici Torgau | 1 | +5 / −1 | update .ignore |
| `79d9c0f` | 2026-03-22 | Heinrici Torgau | 11 | +3619 / −1 | update |
| `ee3aa0a` | 2026-03-22 | Heinrici Torgau | 28 | +20 / −0 | cleanup: remove build artifacts and add gitignore |
| `2d8ade6` | 2026-03-22 | Heinrici Torgau | 4 | +94 / −3 | add crawlernest-autoeval and update license/readme |
| `568d644` | 2026-03-22 | Heinrici Torgau | 1 | +0 / −201 | delet license |
| `3543abf` | 2026-03-21 | Heinrici Torgau | 41 | +340 / −167 | update white paper |
| `63305e1` | 2026-03-20 | Heinrici Torgau | 5 | +500 / −0 | feat: add minimal qs pipeline entry and admissions read-only api |
| `e631763` | 2026-03-20 | Heinrici Torgau | 2 | +269 / −311 | update the guid |
| `7154052` | 2026-03-20 | Heinrici Torgau | 1 | +326 / −675 | update readme/white-paper |
| `5394d1b` | 2026-03-20 | Heinrici Torgau | 29 | +1880 / −173 | update readme/white-paper |
| `d8e5559` | 2026-03-19 | Heinrici Torgau | 2 | +22 / −16 | update readme and white-paper |
| `fbd73f8` | 2026-03-19 | Heinrici Torgau | 34 | +916 / −2088 | 已成功完成 CrawlerNest 從 SQLite 原型資料庫升級到 PostgreSQL 並打通 Java Spring Boot 後端服務的基礎系統整合測試。 |
| `a15af44` | 2026-03-18 | Heinrici Torgau | 2 | +48 / −9 | update white_paper |
| `a432bed` | 2026-03-18 | Heinrici Torgau | 4 | +110 / −22 | message |
| `662375d` | 2026-03-18 | Heinrici Torgau | 46 | +684 / −182 | java模組與主程式資料連接 |
| `124a65f` | 2026-03-18 | Heinrici Torgau | 37 | +198 / −0 | message |
| `aa92ffe` | 2026-03-16 | Heinrici Torgau | 12 | +252 / −2 | update something |
| `47c3905` | 2026-03-16 | Heinrici Torgau | 16 | +117 / −0 | update readme |
| `ff2a3c3` | 2026-03-16 | Heinrici Torgau | 63 | +2759 / −85 | add api servise |
| `aaab5fb` | 2026-03-16 | Heinrici Torgau | 2 | +243 / −26 | update readme and add a license |
| `6a79ba8` | 2026-03-16 | Heinrici Torgau | 1 | +0 / −1 | movie into floder |
| `565cfb8` | 2026-03-16 | Heinrici Torgau | 127 | +0 / −0 | movie into floder |
| `b16eb43` | 2026-03-16 | Heinrici Torgau | 128 | +9264 / −0 | initial crawlernest platform |

---

## 總計

| 項目 | 數值 |
|---|---|
| Commit 數 | 366 |
| 檔案變更累計 | 6205 |
| 新增行數累計 | +1375588 |
| 刪除行數累計 | −699310 |
| 淨增行數 | +676278 |
