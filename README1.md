# CrawlerNest

**CrawlerNest** is an open-source university data infrastructure and web platform.  
It transforms fragmented global education data into structured, queryable knowledge — powering a deterministic decision engine that helps students make data-driven university choices.

> "If Google organizes information, CrawlerNest structures education data."

---

## What It Does

CrawlerNest crawls, normalizes, and warehouses ranking and admission data from 1,500+ universities across 31 countries, then runs an explainable recommendation engine to generate **reach / target / safety** groupings — replacing expensive, opaque consulting with transparent, data-driven guidance.

---

## Current Status (March 2026)

| Module | Status | Scale |
| :--- | :---: | :--- |
| Async crawler pipeline | ✅ Operational | 1,500+ universities |
| PostgreSQL warehouse | ✅ Operational | Transaction-safe with rollback |
| Normalization engine (Python + C) | ✅ Operational | 250,000+ lines · 14/14 tests |
| Java Spring Boot API | ✅ Operational | `/universities` `/rankings` `/admissions` |
| Recommendation engine (v3) | ✅ Operational | Reach / Target / Safety |
| Next.js consumer website | 🔄 In Progress | Rankings browser + recommendation UI |

---

## Architecture

CrawlerNest is built on a decoupled 5-layer system:

```
Data Layer → Canonical Layer → Aggregation Layer → Decision Layer → API & Product Layer
(Crawlers)    (Normalization)   (PostgreSQL)         (Rec Engine)    (Spring Boot + Next.js)
```

---

## Quick Start

### 1. Start the Backend API
```bash
cd crawlernest/servise_for_java
./mvnw spring-boot:run
```

### 2. Start the Frontend
```bash
cd crawlernest/crawlernest-web
npm run dev
```

The application will be available at `http://localhost:3000`.

### 3. Run the Data Pipeline
```bash
# Production-safe run (recommended)
bash crawlernest/scripts/run_production_safe.sh

# Manual run with limit
python3 run_pipeline.py run-qs-universes --ranking-year 2026 --limit 100

# All major rankings (World + 5 regional)
python3 run_pipeline.py run-qs-major --ranking-year 2026
```

---

## Technology Stack

| Layer | Technology |
| :--- | :--- |
| Crawler | Python · AsyncIO · compliance-aware throttling |
| Normalization | Python + C hybrid engine |
| Storage | PostgreSQL (transaction-safe) |
| Backend API | Java Spring Boot |
| Frontend | Next.js (React) |
| Testing | PyTest · JUnit · 14/14 tests passing |

---

## Roadmap

- **Now:** Web platform MVP, expanded regional coverage, AutoEval quality assurance
- **Next (6–18 months):** THE + ARWU data sources, program-level analytics, enhanced entity resolution
- **Future:** Public API platform, LLM-assisted admission verification, AI-driven consulting insights

---

## Organization

- **KAO EN-TSAI** — Founder & System Architect
- **shika tina** — Co-Developer & Data Engineer

Built with AI-assisted development (Claude, ChatGPT, OpenClaw autonomous agent).

---

## License

MIT License — open for research, education, and contribution.

---

## Contact & Links

- GitHub: [github.com/CrawlerNest](https://github.com/CrawlerNest)
- Email: ek2412045@gmail.com
- Pitch Deck: [crawlernest_pitch_deck.pdf](./press/crawlernest_pitch_deck.pdf)
