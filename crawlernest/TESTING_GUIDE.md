# CrawlerNest 全系統測試指南

本文件整合 CrawlerNest 目前所有可執行的測試方式，包含：
- Python 模組測試（crawler / extractor / db writer）
- Java Spring Boot 測試（JUnit / MockMvc）
- C 正規化引擎測試
- API 整合與效能測試
- 資料庫 schema 驗證

## 1. 測試範圍與分層

CrawlerNest 目前測試可分為五層：

1. `Unit`：函式與類別邏輯驗證（Python unittest、Java JUnit）
2. `Module Integration`：模組間資料流驗證（Python 測試組）
3. `Service/API`：REST 端點可用性與回應格式（pytest + requests）
4. `Engine`：C normalization engine 行為驗證（make test）
5. `Data Layer`：SQLite / PostgreSQL schema 與連線驗證

## 2. 測試目錄與入口

主要測試檔案：

- `crawlernest-tests/run_tests.py`：Python 統一測試入口（unittest discover）
- `crawlernest-tests/test_fetcher.py`
- `crawlernest-tests/test_extractor.py`
- `crawlernest-tests/test_db_writer.py`
- `crawlernest-tests/test_ranking_api.py`（含 mock + 可選 live integration）
- `crawlernest-tests/test_regions.py`（外網可達性測試）
- `crawlernest-tests/performance_test.py`（API 壓力測試）
- `servise_for_java/src/test/java/...`：Java 單元與 Web 層測試
- `crawlernest-normalization/c_engine/src/tests/test_normalizer.c`：C 引擎測試

## 3. 環境需求

在專案根目錄（本文件同層）執行：

```bash
cd /Users/test/Desktop/crawlernest/crawlernest
```

### 3.1 Python

- Python 3.9+
- 建議安裝測試依賴：

```bash
python3 -m pip install -U pytest requests
```

### 3.2 Java

- 建議使用 Java 17（`pom.xml` 指定 `java.version=17`）
- 使用專案內建 wrapper：`servise_for_java/mvnw`

### 3.3 C Toolchain

- `gcc`
- `make`

### 3.4 資料庫（選配）

- SQLite（本機檔案型）
- PostgreSQL（若要測試 Java 服務或 PostgreSQL schema）

## 4. 快速測試指令（建議順序）

1. C engine（最快、無外部依賴）
2. Python unit/module tests
3. Java tests
4. API integration/performance（需先啟服務）
5. DB schema/連線驗證

---

## 5. Python 測試

### 5.1 一鍵執行（目前主入口）

```bash
python3 crawlernest-tests/run_tests.py
```

這支腳本會自動將下列模組加入 `sys.path` 後做 `test_*.py` discover：
- `crawlernest-core`
- `crawlernest-extractors`
- `crawlernest-jobs`
- `crawlernest-db-writer`
- `crawlernest-cli`
- `crawlernest-analytics`

### 5.2 單檔執行（unittest）

```bash
python3 -m unittest crawlernest-tests/test_fetcher.py -v
python3 -m unittest crawlernest-tests/test_extractor.py -v
python3 -m unittest crawlernest-tests/test_db_writer.py -v
```

### 5.3 pytest 測試（建議）

```bash
pytest crawlernest-tests/test_ranking_api.py -v
pytest crawlernest-tests/test_regions.py -v
```

`test_ranking_api.py` 裡有 `@pytest.mark.integration` 的 live 測試，預設可用：

```bash
pytest crawlernest-tests/test_ranking_api.py -m integration -v
```

### 5.4 已知狀態（2026-03-20 實測）

1. `run_tests.py` 在未安裝 `pytest` 時，`test_ranking_api.py` / `test_regions.py` 會 import 失敗。
2. `test_db_writer.py` 目前以 `DBWriter(self.test_db)` 初始化，與新版 `DBWriter(db_type="sqlite", db_path=...)` 介面不一致，會報 `Unsupported db_type`。

這兩點屬於測試腳本與當前程式介面不同步，不影響你執行其他測試類別。

---

## 6. C 正規化引擎測試

目錄：`crawlernest-normalization/c_engine`

### 6.1 編譯

```bash
cd crawlernest-normalization/c_engine
make
```

### 6.2 測試

```bash
make test
```

### 6.3 清理

```bash
make clean
```

### 6.4 實測狀態（2026-03-20）

`make test` 可通過（12/12）。

---

## 7. Java 測試（Spring Boot / JUnit）

目錄：`servise_for_java`

### 7.1 執行全部測試

```bash
cd servise_for_java
./mvnw test
```

### 7.2 執行單一測試類

```bash
./mvnw test -Dtest=UniversityServiceTest
./mvnw test -Dtest=UniversityControllerTest
```

### 7.3 測試報告位置

- `servise_for_java/target/surefire-reports/*.txt`
- `servise_for_java/target/surefire-reports/*.xml`

### 7.4 Java 版本注意事項

2026-03-20 實測在 Java 25 會出現 Mockito/ByteBuddy attach 錯誤（`Could not initialize inline Byte Buddy mock maker`）。

建議切回 Java 17 後再跑：

```bash
cd servise_for_java
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
./mvnw test
```

---

## 8. API 整合與效能測試

### 8.1 啟動 Java 服務

```bash
cd servise_for_java
./mvnw spring-boot:run
```

預設服務使用 `http://localhost:8080`。

### 8.2 API smoke test（手動）

```bash
curl -i http://localhost:8080/universities
curl -i http://localhost:8080/rankings
```

### 8.3 pytest API 測試

在另一個終端：

```bash
cd /Users/test/Desktop/crawlernest/crawlernest
pytest crawlernest-tests/test_ranking_api.py -v
```

### 8.4 效能測試

```bash
cd /Users/test/Desktop/crawlernest/crawlernest
python3 crawlernest-tests/performance_test.py
```

此腳本會對 `http://localhost:8080/universities` 做併發請求並輸出：
- Total Requests
- Successful Requests
- Average / Max / Min Latency

---

## 9. 資料庫與 Schema 驗證

### 9.1 SQLite Schema 快速驗證

```bash
cd /Users/test/Desktop/crawlernest/crawlernest
sqlite3 /tmp/crawlernest_schema_test.db < crawlernest-schema/schema.sql
sqlite3 /tmp/crawlernest_schema_test.db ".tables"
```

### 9.2 PostgreSQL Schema 套用驗證

先建立資料庫（例：`clawer`），再套 schema：

```bash
psql -U postgres -d clawer -f crawlernest-schema/postgresql_schema.sql
```

驗證 schema 是否建立：

```bash
psql -U postgres -d clawer -c "\dn"
psql -U postgres -d clawer -c "\dt warehouse.*"
```

### 9.3 Java 服務 DB 設定

`servise_for_java/src/main/resources/application.properties` 目前使用 PostgreSQL：
- `spring.datasource.url=jdbc:postgresql://localhost:5432/clawer`
- `spring.datasource.username=postgres`
- `spring.datasource.password=postgres`

若本機帳密不同，請先改成你的本地設定再做整合測試。

---

## 10. 建議的完整驗證流程（Release 前）

1. `make test`（C engine）
2. `pytest crawlernest-tests/test_fetcher.py crawlernest-tests/test_extractor.py -v`
3. `pytest crawlernest-tests/test_ranking_api.py -v`
4. `./mvnw test`（Java 17）
5. 啟服務後執行 `python3 crawlernest-tests/performance_test.py`
6. 以 `curl` 驗證關鍵端點（`/universities`, `/rankings`）

---

## 11. 常見問題排查

### Q1: `ModuleNotFoundError: No module named 'pytest'`

```bash
python3 -m pip install pytest requests
```

### Q2: Java 測試出現 ByteBuddy/Mockito attach 失敗

改用 Java 17：

```bash
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
cd servise_for_java && ./mvnw test
```

### Q3: API 測試全部 timeout

先確認 Java 服務是否啟動：

```bash
curl -i http://localhost:8080/universities
```

### Q4: PostgreSQL 連不上

檢查：
1. 服務是否啟動
2. `application.properties` 帳密是否正確
3. `clawer` database 是否存在
4. `postgresql_schema.sql` 是否已套用

---

如需把本指南進一步改成 CI（GitHub Actions）版，可再補一份 `ci-testing-guide` 與 workflow 範本。
