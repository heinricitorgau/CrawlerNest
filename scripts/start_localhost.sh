#!/usr/bin/env bash
set -e

echo "[1/3] Using local PostgreSQL..."
pg_isready -U test -d clawer || {
  echo "PostgreSQL is not ready. Please start local PostgreSQL first."
  exit 1
}

echo "[2/3] Starting Spring Boot API..."
cd crawlernest/servise_for_java
./mvnw spring-boot:run &
API_PID=$!

cd ../crawlernest-web

echo "[3/3] Starting Next.js frontend..."
npm run dev &
WEB_PID=$!

echo ""
echo "CrawlerNest localhost started:"
echo "API:  http://localhost:8080"
echo "Web:  http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop API and frontend."

trap "kill $API_PID $WEB_PID" INT
wait
