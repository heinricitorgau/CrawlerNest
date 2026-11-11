---
title: The licence file must stay the verbatim Apache 2.0 text so GitHub can recognise it
author: Heinricitorgau
date: 2026-11-05
branch: main
id: l-71e67fec
scope: repo
status: active
src: agent
touches:
  - crawlernest/crawlernest-kb/databases/arwu_rankings_2026.json
  - crawlernest/crawlernest-kb/databases/the_rankings_2026.json
  - crawlernest/crawlernest-kb/qs_universe_resolution_cache.json
  - crawlernest/crawlernest-kb/qs_universes/2026/global/global/run_status.json
---

## Decided
The project licence is Apache 2.0, kept as the unmodified standard text. The only edit is the copyright line in the appendix: "Copyright 2026 KAO EN-TSAI and CrawlerNest Organization". GitHub now detects it as Apache-2.0.

## Tried and ruled out
- Keeping the old file: several definitions ("Work", "Contribution", "Contributor") had been paraphrased, so GitHub reported NOASSERTION. A reworded licence is also legally murkier than the standard one.
- Switching to MIT to match the owner's other repos: that would change the licence terms, not just fix how GitHub detects them.
- Putting the copyright in a separate NOTICE file: the repo layout rule allows only the READMEs, LICENSE and the four folders at the top level.

## Watch out
Do not reflow, shorten or reword the licence text. Any change other than the appendix copyright line makes GitHub stop recognising it.

In the code: LICENSE (commit 4f03bdd). The standard text comes from `gh api licenses/apache-2.0 --jq .body`. Check detection with `gh api repos/heinricitorgau/CrawlerNest/license --jq .license.spdx_id`.
