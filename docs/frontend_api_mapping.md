# Frontend API Mapping Table (Website MVP)

This document maps the planned MVP React frontend pages to their required `/api/v1` endpoints. It serves as the single source of truth for the data contract between frontend and backend.

All endpoints assume the base path: `/api/v1`

---

## 1. Rankings Page
**Route:** `/` or `/rankings`
**Purpose:** Display the main global aggregated ranking leaderboard.
**Endpoint:** `GET /rankings`
**Request Params:**
- `page` (integer, default 0)
- `size` (integer, default 20)
**Key Response Fields (per item):**
- `canonicalUniversityId` (integer)
- `universityName` (string)
- `country` (string)
- `displayRank` (string)
- `compositeScore` (float)
**UI State Notes:**
- Implement infinite scroll or standard pagination.
- Wrap loading state while fetching.
- Rows should link to `/universities/{slug}`.

---

## 2. University Detail Page
**Route:** `/universities/{slug}`
**Purpose:** Display extensive details, admissions, and historical ranking trends for a single university. Organic SEO-friendly entry point.
**Endpoint:** `GET /universities/by-slug/{slug}` (Fallback: `GET /universities/{id}`)
**Request Params:** Path variable `{slug}` matching the database `school_slug`.
**Key Response Fields:**
- `id` (integer)
- `displayName` (string)
- `country` (string)
- `admissions` (object containing GPA/IELTS/TOEFL requirements)
**UI State Notes:**
- Show a 404 Empty State if the backend returns HTTP 404 (Not Found).
- Show skeleton loader for headers during data fetch.

---

## 3. Recommendation Page
**Route:** `/recommend`
**Purpose:** Form-driven page where students input their profile (Rank target, IELTS, Risk tolerance) and receive grouped reach/target/safety results.
**Endpoint:** `GET /recommendations`
**Request Params:**
- `targetRank` (integer, REQUIRED)
- `ielts` (float, optional)
- `country` (string, optional)
- `riskProfile` (enum: `conservative`, `balanced`, `aggressive`, optional)
- `countryPolicy` (enum: `hard_filter`, `soft_preference`, optional)
**Key Response Fields:**
- `reach`, `target`, `safety` (Arrays of objects)
- Node fields: `universityName`, `matchingScore`, `category`, `explanation`
- `metadata` (object reflecting applied weights and limits)
**UI State Notes:**
- Display results in three distinct vertical columns or tabs (Reach / Target / Safety).
- Use `explanation` string to provide explainable AI tooltips over the `matchingScore`.

---

## 4. Compare Page
**Route:** `/compare?u1={slug1}&u2={slug2}`
**Purpose:** Side-by-side matrix view comparing 2-5 universities.
**Endpoint:** `POST /compare`
**Request Params (JSON Body):**
```json
{
  "identifiers": ["oxford", "lse"],
  "rankingYear": 2026
}
```
**Key Response Fields:**
- `dimensions` (array of strings, e.g. "Rank", "Location", "IELTS")
- `nodes` (array of university capability objects mapped to dimensions)
**UI State Notes:**
- If identifiers are invalid or not found, backend returns `400 Bad Request`.
- Render a fixed left-column table layout iterating over `dimensions`.

---

## Example cURL Requests

### Rankings Data
```bash
curl -X GET "http://localhost:8080/api/v1/rankings?page=0&size=10"
```

### University by Slug
```bash
curl -X GET "http://localhost:8080/api/v1/universities/by-slug/massachusetts-institute-of-technology"
```

### Recommendations (Balanced profile, targeting top 100)
```bash
curl -X GET "http://localhost:8080/api/v1/recommendations?targetRank=100&ielts=7.0&country=United%20Kingdom&riskProfile=balanced&countryPolicy=hard_filter"
```

### Compare POST Request
```bash
curl -X POST "http://localhost:8080/api/v1/compare" \
     -H "Content-Type: application/json" \
     -d '{
           "identifiers": ["oxford", "yale", "nus"],
           "rankingYear": 2026
         }'
```
