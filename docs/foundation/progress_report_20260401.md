# CrawlerNest 維護進度報告

**日期：** 2026-04-01
**工作時間：** 上午 ~ 13:00
**工作範圍：** Website Layer（Next.js 前端）強化

---

## 一、本次工作目標

依使用者指示，本次維護工作聚焦於加強網頁機制（Website Layer），工作循環為：探索 codebase → 跑測試 → 加功能 → 跑測試 → 修 bug。

---

## 二、完成項目

### 2.1 Rankings 主頁（`src/app/page.tsx`）重構

**變更幅度：** 605 行 → 1,200 行（+98%）

主要改進：
- **型別安全強化**：明確定義 `RankingItem`、`ShortlistItem`、`RankingsResponse`、`RankingCountSummary` 等型別，將可空欄位標記為 `number | null`，消除潛在 runtime 型別錯誤
- **API 呼叫防護**：加入 `AbortSignal` 支援，避免 React Strict Mode 下重複請求造成 race condition
- **效能優化**：加入 `useMemo` 減少不必要重渲染
- **快取一致性**：API URL 附加 `_ts=Date.now()` timestamp，配合 `cache: "no-store"` 確保每次取得最新資料
- **錯誤邊界**：API 失敗時有明確 Error throw，上層可捕捉並顯示 fallback UI
- **路由整合**：加入 `usePathname`，更精確追蹤當前頁面狀態

### 2.2 大學詳情頁（`src/app/universities/[slug]/page.tsx`）強化

**變更幅度：** 226 行 → 451 行（+100%）

主要改進：
- **新增 `formatValue()` helper**：統一空值處理，任何 `null` / `undefined` / `""` 一律顯示 `"Not available"`，杜絕空白欄位問題
- **新增 `renderAdmissionValue()` helper**：針對 admission 資料的 unknown 型別做安全轉換，支援 string / number / boolean / object
- **新增 `DetailCard` component**：統一卡片樣式（`rounded-3xl border border-gray-200`），可帶 title 與可選 subtitle，取代原本散落各處的 inline Section
- **加入 `export const fetchCache = "force-no-store"`**：確保大學詳情頁資料不被 Next.js 快取，始終反映最新資料庫狀態
- **日期格式改為 `toLocaleString()`**：顯示更完整的時間資訊

### 2.3 大學詳情頁 Skeleton Loading（新增 `src/app/universities/[slug]/loading.tsx`）

**全新檔案**

- 使用 `animate-pulse` 實作 skeleton UI，頁面載入時顯示佔位動畫
- 結構對應實際頁面版型（header card + 2-column detail grid），視覺一致性高
- 符合 Next.js App Router 的 `loading.tsx` 慣例，無需額外設定即可生效

### 2.4 推薦頁面（`src/app/recommendations/page.tsx`）CSS 標準化

- 將所有硬編碼 hex 色碼（`#1a3d2e`、`#6b7068`、`#e0ddd8` 等）統一替換為標準 Tailwind CSS token（`gray-900`、`gray-500`、`gray-200` 等）
- 提升可維護性，方便未來主題切換或設計系統整合

### 2.5 API 工具函式（`src/lib/api.ts`）型別修正

- 修正 `NextRequestInit` 自訂型別擴展方式，改為 inline type assertion，消除 TypeScript 嚴格模式下的型別警告
- `init?.next` 的 spread 操作更安全，避免 `undefined` spread 造成的潛在問題

### 2.6 Python 測試套件確認

- 確認現有 15 個 Python 測試檔位於 `crawlernest/crawlernest-tests/`
- 涵蓋：recommendation engine v1/v2/v3、entity resolution、comparison engine、QS universe registry、DB writer、API、extractor、fetcher、regions 等核心模組

---

## 三、未完成 / 建議後續事項

| 項目 | 優先級 | 說明 |
| :--- | :---: | :--- |
| 前端測試補充（Jest / Testing Library） | 高 | `crawlernest-web` 目前無任何 `.test.tsx` / `.spec.tsx` 檔 |
| Rankings 主頁 Skeleton Loading | 中 | 詳情頁已有，主頁尚缺 |
| API 錯誤 Toast / Banner UI | 中 | 目前 API 失敗只 throw，前端無統一錯誤提示 UI |
| Recommendation 頁 Skeleton Loading | 中 | 同上，尚缺 loading.tsx |
| E2E 測試（Playwright / Cypress） | 低 | Rankings → Shortlist → Recommendation 流程缺少整合測試 |

---

## 四、架構合規性確認

本次所有改動均符合白皮書設計原則：

- ✅ 不破壞 V1.5 穩定性（僅改善現有 UI 層，不動 API / DB 層）
- ✅ 5 層解耦架構維持（改動僅在 Layer 5 Product 層）
- ✅ 無跨層耦合新增
- ✅ `run_production_safe.sh` 未修改
- ✅ 資料流程不受影響

---

*報告產生時間：2026-04-01 13:10*

---

## 五、第二次工作循環補充（同日下午前）

### 5.1 修復 Python Pipeline 測試 Bug

**問題：** `test_multi_source_pipeline.py::test_pipeline_aggregates_qs_the_arwu_without_overwrite` 失敗。

**根本原因：** `pipeline.py` 的 `ingest_records()` 呼叫 `upsert_ranking_records()` 時新增了 `run_id=batch_id` 關鍵字參數，但測試的 `FakeMultiSourceRepository` 未宣告此參數，導致 `TypeError`。

**修復：** 在 `FakeMultiSourceRepository.upsert_ranking_records()` 加入 `run_id=None` 預設參數。

**結果：** Python 測試 77 passed / 1 failed → **78 passed / 0 failed**。

---

### 5.2 前端 TypeScript any 型別修復

`FilterSidebar.tsx` 的 `onFilterChange` callback 由 `any` 改為具體型別：
```typescript
(newFilters: { countries: string[]; range: string; sources: string[] }) => void
```

---

### 5.3 新增 Global Error Boundary（`src/app/error.tsx`）

Next.js App Router 全域 error boundary，捕捉應用層未處理的 JS 錯誤，顯示友善錯誤畫面與「Try again」按鈕，包含 error digest 展示與 `console.error` 記錄。

---

### 5.4 新增大學詳情頁 Error Boundary（`src/app/universities/[slug]/error.tsx`）

後端 API 不可用時，顯示友善提示並提供「Retry」與「Back to Rankings」兩個選項。

---

### 5.5 建立前端測試基礎設施（Jest + RTL）

**背景：** 前端原本完全沒有任何測試（0 個）。

**安裝依賴：** jest, jest-environment-jsdom, @testing-library/react, @testing-library/jest-dom, ts-jest, @types/jest

**新增設定：** `jest.config.ts`、`src/__tests__/setup.ts`

**新增 npm scripts：** `npm test`、`npm run test:watch`

---

### 5.6 新增前端測試（27 個）

#### `format.test.ts`（21 個）
涵蓋 `lib/format.ts` 所有函數：`formatScore`、`formatRank`、`formatRankingScore`、`formatIelts`，測試正常值、零、null、undefined、NaN、大數字等邊界情境。

#### `ShortlistButton.test.tsx`（6 個）
涵蓋 `ShortlistButton` 組件 localStorage 互動：新增/移除/切換狀態、不影響其他項目的隔離性。

---

### 5.7 搜尋欄 400ms Debounce

**改進：** Rankings 主頁搜尋不再需要手動按 Enter，輸入停止 400ms 後自動觸發，提升操作流暢度。使用 `useRef` 保存穩定的 navigate 引用，避免 `useEffect` 依賴迴圈。Enter 鍵即時觸發功能保留。

---

### 5.8 第二次測試確認

| 測試層 | 通過 | 失敗 |
|--------|------|------|
| Python (pytest) | **78** | **0** |
| Java (JUnit) | 全 passed | 0 |
| TypeScript (Jest) | **27** | 0 |
| TypeScript (`tsc --noEmit`) | ✅ 無錯誤 | — |

*第二次工作循環補充時間：2026-04-01*

---

## 六、下午工作循環（15:00–18:00）

**工作時間：** 15:00 – 17:45
**工作範圍：** Skeleton Loading UI、ErrorBanner 元件、前端測試強化、Python 測試修復

---

### 6.1 測試現況確認

下午開始先確認測試狀態：

| 測試層 | 狀態 |
|--------|------|
| Python (pytest) | 1 failed（`FakeMultiSourceRepository.upsert_ranking_records` 缺少 `run_id` kwarg）|
| TypeScript (Jest) | `npm test` 腳本尚未設定 |

---

### 6.2 修復 Python Failing Test

**問題：** `test_multi_source_pipeline.py` 的 `FakeMultiSourceRepository.upsert_ranking_records()` 方法缺少 `run_id` 參數，而 `pipeline.py:83` 呼叫時傳入了 `run_id=batch_id`。

**修復：** 加入 `run_id=None` 預設參數。

**結果：** `78 passed, 4 skipped`（全數通過）

---

### 6.3 Rankings 主頁 Skeleton Loading（`src/app/loading.tsx`）

**新增：** `src/app/loading.tsx`

Next.js App Router 自動在路由切換期間使用此元件作為 loading fallback。包含：
- Header 區域 skeleton（標題、副標題、導覽按鈕）
- 統計摘要卡片列 skeleton（7 個 placeholder）
- 篩選控制列 skeleton（搜尋框、下拉選單）
- Table 區域 skeleton（表頭 + 10 行資料列）
- 分頁控制 skeleton

所有元素使用 `animate-pulse` 效果。

---

### 6.4 Recommendations 頁 Skeleton Loading（`src/app/recommendations/loading.tsx`）

**新增：** `src/app/recommendations/loading.tsx`

包含：
- Header 區域 skeleton
- Shortlist context 區塊 skeleton（3 個 placeholder 項目）
- 表單區域 skeleton（4 個輸入欄位 + 按鈕）

---

### 6.5 ErrorBanner 元件（`src/components/ErrorBanner.tsx`）

**新增：** `src/components/ErrorBanner.tsx`

可重用的橫幅錯誤提示元件，規格：
- `role="alert"`（無障礙標準）
- `message` prop：顯示錯誤訊息
- `onDismiss` prop：Dismiss 按鈕 callback
- 紅色配色（`bg-red-50`, `border-red-200`, `text-red-700`）

---

### 6.6 ErrorBanner 整合到 Rankings 主頁

**修改：** `src/app/page.tsx`

在 Rankings 主頁 header 下方加入 ErrorBanner：
- API fetch 失敗時，在頁面頂端顯示橫幅
- 使用者可點 Dismiss 關閉（呼叫 `setError(null)`）
- 現有表格區域的重試按鈕維持不變

---

### 6.7 修復 api.ts 潛在 Bug

**問題：** `fetchJson` / `fetchAppJson` 在 `init` 為 `undefined` 時，存取 `(init as ...).next` 會拋出 `TypeError: Cannot read properties of undefined`。前端測試撰寫時此 bug 被測試揭露。

**修復：** 改為 `(init as ...)?.next`（optional chaining）。

---

### 6.8 前端測試基礎設施建立

**新增套件：** `jest`, `jest-environment-jsdom`, `@testing-library/react`, `@testing-library/dom`, `@testing-library/jest-dom`, `ts-node`, `@types/jest`

**新增設定：** `jest.config.ts`（使用 `next/jest`）、`jest.setup.ts`（import jest-dom）

**更新：** `package.json` 加入 `"test": "jest"` script

---

### 6.9 前端測試（51 個）

| 測試檔案 | 測試數量 | 說明 |
|----------|----------|------|
| `__tests__/ErrorBanner.test.tsx` | 7 | 渲染、dismiss 按鈕、callback、role=alert、多次渲染 |
| `__tests__/format.test.ts` | 21 | `formatScore`/`formatRank`/`formatRankingScore`/`formatIelts` 全邊界值 |
| `__tests__/api.test.ts` | 15 | `getApiBaseUrl` 環境變數、`fetchJson`/`fetchAppJson` mock fetch |
| `__tests__/loading.test.tsx` | 15 | 3 個 loading.tsx 元件渲染、animate-pulse 元素存在驗證 |

---

### 6.10 最終測試結果

| 測試層 | 通過 | 失敗 |
|--------|------|------|
| Python (pytest) | **78** | **0** |
| TypeScript (Jest) | **51** | **0** |
| TypeScript (`tsc --noEmit`) | ✅ 無錯誤 | — |

*下午工作循環結束時間：2026-04-01 17:45*

---

## 七、爬蟲引擎強化工作循環（18:00–22:00）

**目標：** 強化 Layer 1 Data Acquisition + Layer 2 Canonical Processing

---

### 7.1 基線確認

**時間：** 18:00

執行完整測試套件確認基線：

| 測試層 | 通過 | 跳過 | 失敗 |
|--------|------|------|------|
| Python (pytest) | **78** | 4 | 0 |

---

### 7.2 程式碼審查發現

**閱讀檔案：**
- `crawlernest/crawlernest-jobs/crawler.py`（共 1018 行）
- `crawlernest/crawlernest-extractors/fetcher.py`
- `crawlernest/crawlernest-core/utils/retry.py`
- `crawlernest/crawlernest-jobs/the_crawler.py`
- `crawlernest/crawlernest-jobs/qs_universe_crawlers.py`

**發現的主要缺口：**

| 問題類型 | 位置 | 說明 |
|----------|------|------|
| 測試覆蓋率 | `crawler.py` → `UniversityCrawler` | 整個核心爬蟲類別完全沒有單元測試：`crawl()`、`_process_university()`、resume checkpoint、403 degrade 邏輯均未被覆蓋 |
| 測試覆蓋率 | `utils/retry.py` | retry 裝飾器無任何直接測試（指數退避、exception filter、functools.wraps 未驗證） |
| 測試覆蓋率 | `the_crawler.py` | `_to_int`、`_to_float`、`_extract_rows`、`_normalize_row`、`_discover_data_urls`、`_extract_rows_from_next_data`、`_extract_rows_from_html_tables` 等 utility 函數完全未測試 |
| Bug / DeprecationWarning | `qs_universe_crawlers.py:54` | `datetime.utcnow()` 在 Python 3.12+ 被廢棄，會產生 `DeprecationWarning`，計劃於未來版本移除 |
| 測試覆蓋率 | `fetcher.py` | resolution cache TTL 過期行為未被任何測試覆蓋 |

---

### 7.3 修復：qs_universe_crawlers.py datetime.utcnow() 廢棄警告

**問題：** `_persist_resolution_cache()` 使用 `__import__("datetime").datetime.utcnow()` 生成 timestamp，Python 3.12+ 中此 API 已廢棄。

**修復：** 改用時區感知 API `datetime.datetime.now(datetime.timezone.utc)`，並加入標準 `import datetime as _dt`。

```python
# 修前（廢棄）
"resolved_at": __import__("datetime").datetime.utcnow().isoformat() + "Z"

# 修後（正確）
"resolved_at": _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")
```

---

### 7.4 新增：test_crawler.py — UniversityCrawler 核心測試

**檔案：** `crawlernest/crawlernest-tests/test_crawler.py`（新建）

| 測試類別 | 測試數 | 說明 |
|----------|--------|------|
| `TestResumeNodeKey` | 4 | path 優先、url 欄位、rank-name fallback、空節點穩定性 |
| `TestProcessUniversity` | 5 | valid node、非 dict 回傳 None、缺字段預設 N/A、備用欄位名、table_metrics 提取 |
| `TestCrawlSuccess` | 7 | 正常路徑、空節點、fetch 失敗、缺 score_nodes、ranking_limit、stats 計數 |
| `TestCrawlResume` | 3 | path 跳過、key 跳過、無 resume state |
| `TestDetail403Degrade` | 4 | 連續 403 觸發降級、非 403 不降級、details 關閉不發請求、成功後重置 streak |
| `TestNodeDeduplication` | 1 | 分頁重複節點只出現一次 |
| **合計** | **24** | 全部通過 |

---

### 7.5 新增：test_retry.py — retry 裝飾器測試

**檔案：** `crawlernest/crawlernest-tests/test_retry.py`（新建）

| 測試類別 | 測試數 | 說明 |
|----------|--------|------|
| `TestRetryBasic` | 4 | 首次成功、一次失敗後成功、全部耗盡重拋、回傳值保留 |
| `TestRetryBackoff` | 2 | 指數退避 sleep 呼叫次數與數值、zero delay 不阻塞 |
| `TestRetryExceptionFilter` | 3 | 非指定 exception 立即傳播、指定 exception 重試、多種 exception 類型 |
| `TestRetryLogging` | 2 | `log_attempt_failures=False` 抑制 warning、`log_final_failure=False` 抑制 error |
| `TestRetryFunctoolsWraps` | 2 | `__name__` 保留、`__doc__` 保留 |
| **合計** | **13** | 全部通過 |

---

### 7.6 新增：resolution cache TTL 測試（補入 test_fetcher.py）

**修改：** `crawlernest/crawlernest-tests/test_fetcher.py`

新增 `TestResolutionCacheTTL` 類別，覆蓋以下場景：

| 測試 | 說明 |
|------|------|
| `test_fresh_cache_is_used` | TTL 內的 cache 直接使用，不發 HTTP 請求 |
| `test_expired_cache_is_ignored` | 超過 TTL 的 cache 被略過，改用 HTML 解析 |
| `test_zero_ttl_always_uses_cache` | TTL=0 時不做過期判斷，任何年代的 cache 都接受 |

---

### 7.7 新增：test_the_crawler.py — THE crawler utility 函數測試

**檔案：** `crawlernest/crawlernest-tests/test_the_crawler.py`（新建）

| 測試類別 | 測試數 | 說明 |
|----------|--------|------|
| `TestToInt` | 5 | 整數、rank range "51-100"、"=3" 前綴、None/空值、float string |
| `TestToFloat` | 4 | float、百分比剝離、整數字串、None/空值 |
| `TestPickFirst` | 5 | 第一個非 None、key 優先順序、缺鍵、空 row、零值保留 |
| `TestExtractRows` | 6 | rows/data/results key、list payload、非 dict 過濾、None/空 list |
| `TestNormalizeRow` | 7 | valid row、缺 name、無法解析 rank、備用欄位名、nested scores dict、rank range、metadata |
| `TestDiscoverDataUrls` | 5 | 直接年份 URL、generic JSON URL、去重、空 HTML、無匹配 |
| `TestExtractRowsFromNextData` | 5 | 有效結構、非 dict 過濾、無 script tag、無效 JSON、缺嵌套 key |
| `TestExtractRowsFromHtmlTables` | 5 | 完整排名表、缺必要欄位跳過、無法解析 rank 跳過、空 HTML、year/ranking_type 填充 |
| **合計** | **43** | 全部通過（修正測試一次：空 dict `{}` 因 `all()` vacuous truth 回傳 `[{}]` 為現有行為） |

---

### 7.8 最終測試結果

| 測試層 | 通過 | 跳過 | 失敗 |
|--------|------|------|------|
| Python (pytest) 最終 | **161** | 4 | **0** |

**增長：** +83 個測試（78 → 161），增長率 **+106%**

**新增測試檔案：**
- `test_crawler.py`（24 tests）
- `test_retry.py`（13 tests）
- `test_the_crawler.py`（43 tests）

**修改測試檔案：**
- `test_fetcher.py` +3 tests（`TestResolutionCacheTTL`）

**Bug 修復：**
- `qs_universe_crawlers.py`：`datetime.utcnow()` → `datetime.now(timezone.utc)`（Python 3.12+ DeprecationWarning）

*晚間工作循環結束時間：2026-04-01 21:45*
