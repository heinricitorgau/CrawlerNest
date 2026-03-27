# CrawlerNest Website MVP

This directory is the one official Next.js frontend for the CrawlerNest Website MVP.

## App root

Run frontend commands from:

```bash
/Users/test/Desktop/crawlernest/crawlernest-web
```

## Development

```bash
cd /Users/test/Desktop/crawlernest/crawlernest-web
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
