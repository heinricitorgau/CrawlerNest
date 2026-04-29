# CrawlerNest

CrawlerNest 是一個端到端的大學資料基礎設施與網站平台，涵蓋全球排名、學科排名、申請訊號與本機探索流程。

這是一個 data-first 系統：UI 讀取 warehouse 與 analytics view，crawler 與 pipeline 負責把資料整理成 canonical records 並寫入 PostgreSQL。

## 快速啟動

建議用這個流程完整啟動本機環境。

### 1. 建立 Python 環境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 啟動 PostgreSQL

推薦使用 Docker：

```bash
docker compose -f docker-compose.postgres.yml up -d
```

如果尚未安裝 Docker：

```bash
brew install --cask docker
```

也可以使用本機 PostgreSQL：

```text
database: clawer
user: test
host: localhost
port: 5432
```

### 3. Bootstrap schemas 與 seed data

新環境先執行一次；這個指令可以安全重跑。

```bash
python3 -m crawlernest.run_pipeline bootstrap-postgres \
  --pg-user test \
  --pg-database clawer
```

### 4. 初始化排名資料

沒有資料時，網站會顯示空結果。

```bash
./.venv/bin/python -m crawlernest.run_pipeline run \
  --limit 20 \
  --ranking-year 2026 \
  --pg-user test \
  --pg-database clawer
```

### 5. 啟動本機服務

```bash
./scripts/start_localhost.sh
```

這個 script 會用專案預設值啟動本機 API 與 Web。

## 服務位置

```text
Web: http://localhost:3000
API: http://localhost:8080
Agent API: http://localhost:8090
```

主要頁面：

```text
全球排名: http://localhost:3000/rankings
學科排名: http://localhost:3000/subject-rankings
Agent: http://localhost:3000/agent
```

## Subject Rankings MVP

學科排名是獨立的 read path，不是 global ranking aggregation 的延伸。

目前 MVP 支援：

```text
source: QS
year: 2026
subjects:
  - computer-science
  - electrical-engineering
```

載入 QS 學科排名資料：

```bash
./.venv/bin/python -m crawlernest.run_pipeline run-qs-subject \
  --subject computer-science \
  --year 2026 \
  --pg-user test \
  --pg-database clawer
```

```bash
./.venv/bin/python -m crawlernest.run_pipeline run-qs-subject \
  --subject electrical-engineering \
  --year 2026 \
  --pg-user test \
  --pg-database clawer
```

Subject Ranking API 範例：

```bash
curl "http://localhost:8080/api/v1/subject-rankings/subjects"
curl "http://localhost:8080/api/v1/subject-rankings?subject=computer-science&year=2026&page=1&pageSize=20"
```

Web proxy 範例：

```bash
curl "http://localhost:3000/api/subject-rankings/subjects"
curl "http://localhost:3000/api/subject-rankings?subject=computer-science&year=2026&page=1&pageSize=20"
```

## 資料可見性

全球排名 UI 讀取：

```text
warehouse.ranking_record
analytics.v_aggregated_rankings_latest
```

學科排名 UI 讀取：

```text
warehouse.subject_ranking_record
analytics.v_subject_rankings_latest
```

Raw 與 staging tables 是 pipeline 輸入，不會直接顯示在產品 UI。

## 手動開發模式

啟動 Spring Boot API：

```bash
cd crawlernest/servise_for_java
./mvnw spring-boot:run
```

啟動 Next.js Web：

```bash
cd crawlernest/crawlernest-web
npm install
npm run dev
```

執行常用檢查：

```bash
python3 crawlernest/scripts/smoke_subject_rankings.py
cd crawlernest/crawlernest-web && npm run build
cd crawlernest/servise_for_java && ./mvnw -q -Dtest=SubjectRankingApiIntegrationTest test
```

## 常見問題

### Port 8080 被佔用

```bash
lsof -i :8080
kill -9 <PID>
```

### UI 沒有資料

先執行 pipeline，再重新整理頁面：

```bash
./.venv/bin/python -m crawlernest.run_pipeline run \
  --limit 20 \
  --ranking-year 2026 \
  --pg-user test \
  --pg-database clawer
```

如果是學科排名頁，也需要針對想看的 subject 執行 subject loader。

### 學科排名頁能開，但表格是空的

確認 subject pipeline 有寫入資料，而且 Java API 正在執行：

```bash
python3 crawlernest/scripts/smoke_subject_rankings.py
curl "http://localhost:8080/api/v1/subject-rankings?subject=computer-science&year=2026"
```

### 找不到 Docker

安裝 Docker Desktop：

```bash
brew install --cask docker
```

## 建議開發流程

```text
1. 啟動 PostgreSQL
2. 執行資料 pipeline
3. 啟動 API 與 Web
4. 打開 /rankings 或 /subject-rankings
5. 先從 warehouse/analytics views 查資料，再 debug UI
```

CrawlerNest 以 correctness-first 為原則。當畫面看起來不對時，先確認 data pipeline 與 warehouse views，再修改產品層。
