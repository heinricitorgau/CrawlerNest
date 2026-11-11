# QS 歷年封存資料載入器:設計

狀態:**設計草案,尚未實作,等待決定**(見最後一節)。
依據:2026-10-02、10-03 對 Wayback Machine 的乾跑,以及對 `run_pipeline.py`、`qs_adapter.py`、
`rank_delta.py`、`multi_source/pipeline.py` 的閱讀。

## 1. 目標與非目標

**目標:** 把 QS 世界大學排名 2016、2018–2020、2022–2024 的歷年榜單,從 Internet Archive 保存的
QS 官方資料檔還原,走現有的 entity resolution 與 ingest 流程寫入資料庫,且每一筆都能追溯到
哪個快照。

**非目標:**

- 不繞過 Cloudflare,不修改 live crawler(`qs_universe_crawlers.py`、`transport.py`、`fetcher.py`)。
- 不手抄任何一列,不用其他來源補值。
- 不決定對使用者如何揭露(見第 8 節)。
- 不改 `DATASET_COVERAGE` / `DATASET_YEARS`,ingest 後維持 shadow。
- 不處理 2015(edition 證據較弱,等決定)、2017(QS 沒有這個 edition)、2021(沒有封存資料檔)。
  **2026-11-10 更正:** 這一行寫下時的三個理由,有兩個已經不成立,見文末同日備註。
  2015 與 2021 現在釘在 manifest 裡,但仍然沒有 ingest。

## 2. 為什麼是獨立模組

`ranking_edition.py` 的 edition 證明,是對「crawler 實際讀到的頁面」做驗證。若把封存內容塞進
live crawler 的 HTTP 層,驗證仍會通過,但驗證的對象已不是 QS 官方頁面,證據欄位會說謊。
所以載入器自己抓、自己驗證,輸出自己標明來源性質的檔案,只在最後一步與現有流程會合。

## 3. 輸入:人工審核過的 manifest

載入器**不自己挑快照**。快照的選擇是人要審核的決定(見第 9 節),結果固定寫進 manifest,
載入器只照 manifest 做事,同樣輸入永遠得到同樣結果。

位置:`crawlernest/crawlernest-kb/qs_archive/manifest.json`

```json
{
  "2024": {
    "ranking_year": 2024,
    "edition_page": {
      "snapshot_url": "https://web.archive.org/web/20230627200422id_/https://www.topuniversities.com/university-rankings/world-university-rankings/2024",
      "snapshot_ts": "20230627200422"
    },
    "data_file": {
      "snapshot_url": "https://web.archive.org/web/20260329044711id_/https://www.topuniversities.com/sites/default/files/qs-rankings-data/en/3897789.txt",
      "snapshot_ts": "20260329044711",
      "expected_ranking_id": "3897789",
      "expected_sha256": "<首次審核時記錄,之後每次比對>"
    },
    "reviewed_by": "<人>",
    "reviewed_on": "2026-10-xx",
    "notes": "資料檔只有這一個快照,距發布約 33 個月"
  }
}
```

`expected_sha256` 讓審核後的內容被鎖定:Wayback 的內容若有變,載入器拒絕執行,而不是悄悄吃進新內容。

初始候選(2026-10-02/03 乾跑):

| 年份 | 資料檔 id | 備註 |
|---|---|---|
| 2016 | 326584 | 2 個內容不同的快照,選用前要比對差異 |
| 2018 | 357051 | 同上 |
| 2019 | 397863 | 同上 |
| 2020 | 914824 | 1 個快照 |
| 2022 | 3740566 | 4 個快照,edition 頁面要用較晚的快照才通過驗證 |
| 2023 | 3816281 | 1 個快照,edition 頁面同上 |
| 2024 | 3897789 | 1 個快照 |

## 4. 流程

新模組 `crawlernest/crawlernest-jobs/qs_archive_loader.py`,階段之間以明確的 dataclass 傳遞,
每個階段失敗就停,不退回其他來源。

```
manifest ─▶ fetch ─▶ verify_edition ─▶ parse ─▶ guards ─▶ write_artifact ─▶ [ingest]
```

### 4.1 fetch

- 只讀 Wayback 的 `id_` 原始內容 URL。節流(每個請求間隔 ≥ 2 秒)、不併發、有限次重試,
  遇到 "Temporarily Offline" 或 5xx 要退避重試(乾跑時真的遇到)。
- 注入 `Fetch` 型別的函式(與 `ranking_edition.Fetch` 相同簽章),測試時不碰網路。
- 原始回應(gzip 解壓前)寫到 `qs_archive/raw/<year>/`,記錄 sha256。
- 內容若是 gzip(Wayback 對這些檔案是),先解壓。

### 4.2 verify_edition

直接重用 `ranking_edition.verify_qs_edition_page`,對**封存的 edition 頁面 HTML** 驗證:

- 頁面 `<title>` 只命名 manifest 的那一年。
- 頁面宣告**恰好一個** ranking id。
- 資料檔的 id(檔名)等於該 id,且等於 manifest 的 `expected_ranking_id`。
- 資料檔內容的 sha256 等於 `expected_sha256`。

任何一項失敗就拒絕,丟 `EditionMismatchError`。

### 4.3 parse

封存的資料檔是 `{"data": [...]}`。欄位(以 2024 為例):`core_id, country, city, nid, title, logo, score, rank_display, region, …`。

- `title` 是 HTML(`<div class="td-wrap"><a href="/universities/…" class="uni-link">校名</a></div>`),
  要去標籤取校名,`href` 取 `/universities/...` 當 `qs_profile_path` / `path`。
- `score` 對應 `table_metrics["Overall Score"]`(`QSAdapter` 從這個鍵讀分數)。
- 轉成現有的 `models.University`,讓之後能走與 live crawl 相同的 `QSAdapter`。
- **沒有任何欄位用猜的。** 缺欄位就留空,不補。

### 4.4 名次處理(依 2026-10-03 對 adapter 的閱讀)

現有流程對 QS 2026 存的是端點的逐列序號,而歷年封存檔(2016–2024)**沒有**這個序號,只有
`rank_display`。直接餵進去,`_safe_int("=196")` 與 `_safe_int("201-210")` 都回傳 `None`,
約 85% 的列名次為空,而分析層以 `rank_position IS NOT NULL` 過濾,這些大學會靜默消失。

載入器的規則(沿用 ARWU / THE 的既有慣例:`rank_position` 存區間下界):

| `rank_display` | `University.rank` | 說明 |
|---|---|---|
| `85` | `"85"` | 精確 |
| `=196` | `"196"` | 並列,取名次 |
| `201-210` | `"201"` | 區間下界 |
| `1401+` | `"1401"` | 開放區間下界 |
| `NA` / `N/A` / 空 | `"N/A"` | 不 ingest,列入報告 |

- 用 `rank_delta.parse_rank_band` 解析,不重寫一套。
- **原始的 `rank_display` 一律保留**(`QSAdapter` 已寫入 `metadata.rank_display`)。
- **不用檔案列順序替區間內的大學編造序號**,也不使用 2015 檔裡的序號,讓所有歷年資料語意一致。
- 已知後果:QS 的 `rank_position` 在 2025–2026 是序號、2016–2024 是區間下界,語意不同。
  任何程式直接比較這兩者的 `rank_position` 都會得到錯的結論,只能用 `rank_display` 做區間運算。
  這個限制必須進揭露設計(第 8 節)。

### 4.5 guards(寫檔前的閘門)

會讓整次載入失敗的:

- 列數 < 800(`ranking_edition` 之外的最低合理值,依 2016–2024 實測 933–1,498 設定,可調)
- `nid` 有重複
- 缺校名或缺國家的列超過 1%
- 依檔案順序,區間下界不是非遞減
- 第一名不是精確名次

只警告、交給人審的:

- 與相鄰已載入年份的前 50 名重疊度不在 35–50 之間
- 列數與相鄰年份相差超過 25%
- 列數與 QS 當年公布的總數不符(需要人工提供對照值)

### 4.6 write_artifact

輸出 `crawlernest/crawlernest-kb/databases/qs_rankings_<year>.json`,與 ARWU / THE 檔案同結構
`{"metadata": …, "rows": […]}`,但 metadata 誠實標示來源:

```json
"metadata": {
  "source": "QS",
  "ranking_type": "world",
  "ranking_year": 2024,
  "source_kind": "web_archive",
  "archive_snapshot_url": "https://web.archive.org/web/20260329044711id_/…/3897789.txt",
  "original_url": "https://www.topuniversities.com/sites/default/files/qs-rankings-data/en/3897789.txt",
  "snapshot_timestamp": "20260329044711",
  "retrieved_at": "<載入當下的 UTC 時間>",
  "payload_sha256": "<…>",
  "edition": {
    "source": "QS", "ranking_year": 2024, "verified": true,
    "page_url": "<封存頁面快照 URL>",
    "evidence": "title: … ; archived page declares ranking id 3897789 = data file id",
    "ranking_id": "3897789"
  },
  "row_count": 1498,
  "rank_counts": {"exact": 0, "tied": 0, "banded": 0, "open_ended": 0, "unranked": 0}
}
```

`.gitignore` 目前只忽略 `the_rankings_*.json`,不忽略 `qs_rankings_*`;
`qs_archive/raw/` 的原始回應體積大,要先決定是否 commit(建議只 commit manifest 與 sha256,
原始檔不進 git)。

### 4.7 ingest(預設關閉,要明確旗標)

不修改 `QSAdapter`,也不修改 `sync_qs_multi_source_rankings`。載入器自己組裝:

1. `QSAdapter(ranking_year=y, source_version=f"web_archive:{snapshot_ts}")`
   (`QSAdapter` 本來就有 `source_version` 參數,只是 `sync_qs_multi_source_rankings` 沒傳)。
2. `adapt()` 之後,對每筆 `StandardizedRankingRecord.metadata` 補上
   `provenance`(來源性質、快照 URL、時間戳、sha256)。這個 `metadata` 是普通 dict,可直接補。
3. 用 `MultiSourceRankingPipeline.ingest_records(…, batch_id=<帶時間戳>, ranking_type="world")`
   寫入。`batch_id` 必須有,否則 prune 邏輯會失效。
4. entity resolution 照現有流程。**載入器不新增 alias,不改比對規則。**
   對不到 canonical university 的列照現有機制進未對應名單,並在報告中列出。

**ingest 前的保護(載入器自己強制):**

- 現有的 shrink guard 只在該來源與年份「已有資料」時才生效
  (`pipeline.py` 的 `if existing and count < existing * MIN_RETAINED_RATIO`),
  對空的年份毫無作用,2026-10-02 那筆 QS 2024 異常就是這樣漏掉的。
  所以載入器要自己檢查:該年份 QS 已有資料時拒絕,除非明確傳 `--replace`。
- 要求先完成 `pg_dump` 備份(檢查備份檔存在且是今天的)。
- 記錄這次寫入的 `run_id`、`aggregation_run_id`,輸出可整批還原的指令。
- 不論 ingest 成功與否,都不碰 `DATASET_COVERAGE`。

### 4.8 CLI

新增子命令 `load-qs-archive`(登錄點:`pipeline_command_router.py` 與 `run_pipeline.py` 的 argparse):

```
load-qs-archive --year 2024              # 預設:fetch + verify + parse + guards + 寫檔,不碰資料庫
load-qs-archive --year 2024 --ingest     # 另外 ingest(需先備份,見上)
load-qs-archive --year 2024 --ingest --replace   # 該年份已有 QS 資料時才可用
```

## 5. 順帶發現的 crawler 缺口(獨立工作項,不屬於載入器)

`_load_known_good_qs_snapshot`([run_pipeline.py:435](../../crawlernest/run_pipeline.py))
只要先前的 `run_status.json` 是 `ok`、edition 已驗證、快照非空,就當成可信備援,**不檢查列數**;
備援取得的資料再被無條件 ingest,事後才標成 `degraded`。建議另開一項:

- 備援快照列數低於已知該版本合理下限時拒絕載入。
- `run_backing = fallback_snapshot` 時不寫入分析層,除非明確旗標。

這會修改 live crawler,需要你授權才動。

## 6. 測試(離線,不碰網路)

新增 `crawlernest-tests/test_qs_archive_loader.py`,並加進 `run_tests.py` 的 `test_modules`
(不加的話 CI 不會跑)。用小型 fixture,涵蓋:

- 頁面標題年份與 manifest 不符 → 拒絕
- 頁面宣告多個 ranking id → 拒絕
- 頁面 id 與資料檔 id 不一致 → 拒絕
- sha256 與 manifest 不符 → 拒絕
- gzip 與非 gzip 回應都能解析
- HTML 標題去標籤、`href` 取出 profile path
- 名次轉換:`85`、`=196`、`201-210`、`1401+`、`NA`、`N/A`
- 區間下界非遞減檢查、列數下限、重複 `nid`
- 輸出 metadata 的 `source_kind` 是 `web_archive`,且 `verified` 只有在所有驗證通過時才為 true
- 該年份已有 QS 資料時,`--ingest` 拒絕
- 重複執行同樣輸入,輸出位元組一致
- 對一個**不是**由載入器產生的檔案,不會被誤認為封存資料

## 7. 實作分階段

| 階段 | 內容 | 碰資料庫 |
|---|---|---|
| P0 | manifest、fetch、verify、parse、guards、寫檔,先只做 2024 | 否 |
| P1 | 離線測試,CI 通過 | 否 |
| P2 | 其餘 6 個年份產生檔案,逐年人工審核報告 | 否 |
| P3 | 先備份,pilot ingest 2024,用 SQL 查證(`universe_type='global'`) | 是 |
| P4 | 其餘年份 ingest | 是 |
| P5 | 揭露設計完成後,才討論 `DATASET_COVERAGE` | — |

## 8. 揭露(等你決定,載入器只負責提供材料)

載入器會留下:`source_version = "web_archive:<ts>"`、每筆 `metadata.provenance`、
`metadata.rank_display`。要讓使用者看得到來源性質,需要:

- per-edition 的 caveat(Python `core/caveats.py`、Java `AnalyticsService` 常數、
  `caveatMessages.ts`、`ANALYTICS_EXPLAINABILITY.md` 四份同步,並通過 `test_caveat_contract.py`)
- `DATASET_COVERAGE` 的 QS 年份擴充(`ranking_edition` 的註解警告過:只擴年份、不改措辭,
  會讓快照 caveat 對 QS 說出具體卻不實的話)

這些都不在載入器範圍。

## 9. 需要你決定的事

1. **manifest 的快照挑選政策。** 2016、2018、2019 各有 2 個內容不同的快照,2022 有 4 個。
   建議:挑選前先逐校比對差異,再決定「最早」或「最晚」。這是人工審核步驟,不是載入器的邏輯。
2. **2015 要不要收。** 建議不收(頁面沒宣告 ranking id,過不了現有驗證)。
   **2026-11-10 更正:** 括號裡的理由只對 2015-09 與 2016-04 兩個快照成立。
   2016-11 到 2019-11 的快照通過現有驗證,見文末同日備註。要不要收仍然是你的決定。
3. **名次慣例。** 建議沿用 ARWU / THE 的區間下界,見 4.4。
4. **`qs_archive/raw/` 原始檔進不進 git。** 建議不進,只進 manifest 與 sha256。
5. **要不要同時處理第 5 節的 crawler 缺口。** 建議獨立處理,先於 P3。
6. **揭露設計。** 必須在 P5 之前決定,但不阻擋 P0–P4。

**備註(2026-10-04):備份檔搬家。** 這個載入器的預設備份資料夾現在是 `.local/backups/`(原本在倉儲根目錄的 `backups/`,
所有執行期資料夾都收進了被 gitignore 的 `.local/`)。`crawlernest-kb/qs_archive/receipts/` 裡 2026-10-02/03 寫下的收據是當時的紀錄,
沒有改寫:它們記錄的備份路徑 `…/backups/…dump` 與其中的 `pg_restore` 指令,實際檔案現在在 `…/.local/backups/…dump`。

**備註(2026-11-10):重查 2015、2017、2021。** 用載入器自己的規則重新查了 Internet Archive,結論和第 1 節、第 9 節當初寫的不同。
以下兩個版次已加進 `manifest.json`,**沒有 ingest**,`DATASET_COVERAGE`、`DATASET_YEARS`、`DATASET_ARCHIVE_EDITIONS` 都沒動。

- **2021:有封存資料檔。** `en/2057712.txt` 有 9 個 HTTP 200 的快照,8 個讀得出來,共 6 種不同內容。
  edition 頁面在 2023-08 之後的快照只宣告 `2057712` 一個 id,通過驗證;2021-03 到 2022-09 的快照宣告多個 id,過不了單一 id 規則;
  2020-06 的快照宣告的是 `946820`(QS 最初發布的那張表,不在 `en/` 底下,載入器不能釘)。
  釘的是最早的快照(2021-02-12):1,186 列、1,159 列有名次,`load_year` 回 `written`,一個警告(6 列名次順序差 1)。
  **和 2018、2019、2022 不同,這 6 種內容不只是成員增減**:2021-03-02 的快照改了 4 列的 `rank_display`
  (兩組並列加上 `=`、Rochester 166→165、Brno 701-750→651-700),之後的快照還少了幾列、17 校的國家變空白。
  最早的快照在每一個確切名次上都和最初那張表一致,但多出 184 列(157 列印成 `1001+`,27 列沒有名次);
  這 184 列是否屬於 QS 當時發布的 2021 版次,沒有查證。
- **2015:通過現有驗證。** 「頁面沒宣告 ranking id」只對 2015-09、2016-04 兩個快照成立。
  2016-11 到 2019-11 的五個快照都只宣告 `299926` 一個 id,標題是「QS World University Rankings® 2015/16」。
  `en/299926.txt` 有 2 個可用快照(916 列與 914 列),釘的是較早的那個(2021-02-17):916 列、890 列有名次,
  `load_year` 回 `written`,一個警告(1 列沒有國家)。
- **2017:封存裡沒有這個網址的頁面。** CDX 索引沒有 `/university-rankings/world-university-rankings/2017` 的任何快照。
- **QS 後來改了舊版次的標題。** `/2015` 頁面從 2020 年起標題是「QS World University Rankings 2016」;
  `/2016` 頁面在釘選快照(2016-09)的標題是「…2016」,2020 年之後是「…2017」。
  所以照 QS 現在的標題,倉儲裡的 QS 2016(id `326584`,2016 年 9 月發布)是 2017 版次,
  2015/16 那張表(id `299926`)是 2016 版次,2016、2017、2018 之間沒有缺口。
  這個專案的年份取自頁面網址與釘選快照當時的標題,這次沒有改任何一個已 ingest 版次的標籤。

需要你決定的事,接在第 9 節之後:

7. **2015 與 2021 要不要 ingest。** 兩者都通過載入器的全部規則。ingest 會改 `DATASET_COVERAGE`,是資料遷移,不是改設定。
8. **2021 要釘哪一個快照。** 6 種內容裡名次本身不同,第 9 節第 1 項「逐校比對後再決定」的建議在這裡更重要。
9. **已 ingest 的 QS 2016 要不要改標為 2017。** 改了就和 QS 現在的標題一致,也補上「缺 2017」;
   不改就維持「年份取自頁面網址」這條規則。兩種做法都說得通,但只能選一種,而且 2015 的標籤要跟著同一條規則走。

**決定(2026-11-11,倉儲擁有者):第 7–9 項。**

- **7. 2015 與 2021:不 ingest。** 兩筆釘選移到 `manifest.json` 的 `_not_ingested` 底下。`load_manifest` 跳過所有以 `_`
  開頭的鍵,所以 `--all --ingest` 也碰不到它們。紀錄保留,方便日後重新評估。
- **8. 2021 的快照:** 不 ingest,因此不選。
- **9. QS 2016 改標為 2017:已執行。** 年份規則改為「QS 現在給這個頁面的標題」。
  - manifest 的 2017 項帶 `page_year: 2016`(頁面網址仍是 /2016)與 `label_basis`(誰、何時、為什麼)。
    載入器只有在 `label_basis` 存在時才接受網址年份與標籤不同。
  - edition 頁面改釘 2020-01-02 的快照:標題是「QS World University Rankings 2017」,只宣告 `326584` 一個 id,
    所以載入器用 live crawler 的同一條規則證明它是 2017。資料檔與 sha256 不變(2016 項的同一份)。
    自 2020 年起抽查的十個 /2016 快照中,四個通過 2017 規則,全部宣告 `326584`;取最早的。
  - 倉儲:先以 `qs_archive_loader.py --year 2017 --ingest` 匯入 2017(890 列 matched、24 unresolved,和 2016 相同,
    匯入前自動備份),再以 `crawlernest/scripts/retire_relabelled_qs_edition.py --old-year 2016 --new-year 2017`
    退役 2016:它先確認 890 所大學在兩年的名次與印出名次完全相同,才備份、刪除 890 列 QS 2016、
    刪除 72 列 QS 2016 missing-entity 紀錄,並重算 2016 的彙總(842 列,不再有 QS)。兩份收據都在 `receipts/`。
  - 依同一條規則,/2015 那張表(現在標題「2016」)會是 2016 版次;它在 `_not_ingested`,沒有 ingest。
  - 因此 QS 現在缺 2015、2016、2021。
