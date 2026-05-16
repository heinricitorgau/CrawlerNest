# CrawlerNest Website MVP

This directory is the one official Next.js frontend for the CrawlerNest Website MVP.

## Development

From the repo root:

```bash
cd crawlernest/crawlernest-web
npm install
npm run dev
```

The app runs on `http://localhost:3000`.

## Homepage

The active homepage is:

```text
src/app/page.tsx
```

## Backend API

The current homepage fetches ranking data from:

```text
http://localhost:8080/api/v1/rankings
```

Start the backend API on `localhost:8080` before testing the rankings table.
