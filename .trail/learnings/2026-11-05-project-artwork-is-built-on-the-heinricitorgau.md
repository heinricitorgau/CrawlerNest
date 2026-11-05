---
title: "Project artwork is built on the green beetle logo, not invented emblems"
author: Heinricitorgau
date: 2026-11-05
branch: main
id: l-396bb820
scope: repo
status: active
src: agent
touches:
  - crawlernest/crawlernest-kb/databases/arwu_rankings_2026.json
  - crawlernest/crawlernest-kb/databases/the_rankings_2026.json
  - crawlernest/crawlernest-kb/qs_universe_resolution_cache.json
  - crawlernest/crawlernest-kb/qs_universes/2026/global/global/run_status.json
  - crawlernest/crawlernest-web/src/app/icon.png
  - docs/assets/images/crawlernest-banner.svg
  - README.md
  - README.zh-TW.md
---

## Decided
CrawlerNest's visual identity is the green beetle from the web app's icon. The owner asked for project artwork, such as the README banner, to be built on that logo, not on invented emblems. The banner embeds the beetle itself, unredrawn, on a light circular badge with the green taken from the logo.

## Tried and ruled out
- A made-up "nest with three eggs" emblem: the owner rejected it because it was not the project's own logo.
- Putting the beetle straight onto the dark card: its black legs disappear against it.
- Linking the PNG from the SVG: GitHub renders README SVGs as sandboxed images, so an external or relative image inside the SVG does not load. The logo has to be inlined as base64.

## Watch out
The banner SVG is about 60 KB because the logo is inlined. Shrink the PNG (crop, resize, quantise) rather than linking to it.

In the code: logo source is crawlernest/crawlernest-web/src/app/icon.png (1024x1024 RGBA; the beetle sits in the crop box 237,185 to 787,745). The banner is docs/assets/images/crawlernest-banner.svg, referenced at the top of README.md and README.zh-TW.md. Accent colour is #7ed957 on a #07120b to #15301f gradient.
