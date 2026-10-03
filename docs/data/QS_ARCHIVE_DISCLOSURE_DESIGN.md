# QS 歷年封存資料與 THE 歷年資料:揭露設計

狀態:**方案 A 已於 2026-10-03 採用並實作(含 THE 2015–2024 一併發布)。** 下文保留原提案;
實作時有三處與提案不同,見文末〈7. 實作時的偏離〉。依據 2026-10-03 對 `caveats.py`、
`DatasetScope.java`、`AnalyticsService.java` 的閱讀。我沒有啟動 API 實際驗證輸出,
下面標「推論」的地方都是讀程式碼得到的。

## 1. 現在的狀態有一個矛盾,而且是目前就存在的

資料庫已經有:

| 來源 | 年份(global 榜) | 取得方式 |
|---|---|---|
| ARWU | 2015–2026 | 官方 crawler(2026-09-20 已發布) |
| THE | 2015–2026 | 官方 crawler(協作者 2026-10-02 批次抓取) |
| QS | 2016、2018–2020、2022–2024、2025–2026 | 前者來自封存資料,後兩者來自官方 crawler |

但 `DATASET_COVERAGE` 仍是 QS 與 THE 只有 2025、2026。服務層的邊緣 caveat 是從它產生的
(Python `edition_caveats`、Java `AnalyticsService.editionCaveats(year)`,兩者互為鏡像),
所以對 2024 年的回應,依程式碼推論會說:

> The 2024 edition holds ARWU ranks only. No QS or THE rank exists for this edition, so a
> position here rests on one source rather than on agreement between several.

這句話對 2016、2018–2020、2022–2024 現在是**假的**:資料庫裡這些年份都有 QS 與 THE 的排名,
而 Java 讀 `source_ranks_json` 時沒有按來源過濾(推論:`SourceIntelligenceService`、
`ComparisonService` 等直接讀該欄位),所以排名會被顯示,信心度也會計入。
Java 的來源覆蓋 caveat 是「數資料庫」產生的,會跟著算出實際筆數,但不會說明來源性質。

換句話說,「ingest 後維持 shadow」只對**年份**有效(2024 本來就是已發布年份,因為 ARWU),
對**來源**無效。這是我在先前設計與給協作者的 prompt 裡的錯誤前提,THE 2015–2024 的 ingest
也受同樣影響。API 目前沒有在跑,所以還沒有人讀到。**在重新啟動 API 之前必須解決。**

## 2. 讀者需要知道什麼

對 THE 2015–2024(官方 crawler,與 2025/2026 同等級):只需要把它納入覆蓋表,
沿用 ARWU 2015–2024 的發布方式即可,不需要新的 caveat 類型。

對 QS 歷年封存資料,有四件事是現有 caveat 沒有說的:

1. **來源性質:** 資料來自 Internet Archive 保存的 QS 資料檔,不是我們直接抓的。
2. **時間:** 快照時間可能晚於發布很久(2016 約 5.6 年、2023 約 3.9 年),QS 之後可能修訂過。
3. **名次語意:** QS 大多以並列或區間公布名次。這些年份的 `rank` 是印出名次的下界,
   2025、2026 年則是逐校序號,兩者**不能直接比較**。
4. **彙總:** 含這個名次的 composite 與信心度,是在區間下界之上算的。

另外已存在、需要一併說明的缺口:QS 沒有 2015、2017(QS 沒有這個 edition)、2021(沒有可還原的資料檔)。
這個由現有的「edition 缺哪些來源」caveat 處理,擴充覆蓋表之後自然正確。

## 3. 設計

### 3.1 資料:覆蓋表加年份,另加一張「封存來源」表

```python
DATASET_COVERAGE = {
    "QS":   (2026, 2025, 2024, 2023, 2022, 2020, 2019, 2018, 2016),
    "THE":  (2026, 2025, 2024, ..., 2015),        # 連續
    "ARWU": (2026, ..., 2015),
}

#: 哪些 (來源, 年份) 不是我們直接 crawl 的,以及快照日期。
DATASET_ARCHIVE_EDITIONS = {
    "QS": {2024: "2026-03-29", 2023: "2026-05-10", 2022: "2022-04-09", 2020: "2021-02-16",
           2019: "2021-02-21", 2018: "2021-02-12", 2016: "2022-04-26"},
}
```

`DATASET_ARCHIVE_EDITIONS` 的值**不是手寫的事實**,要有測試把它釘在
`crawlernest-kb/qs_archive/manifest.json` 與 `receipts/` 上,不一致就失敗,
避免這個常數和實際 ingest 的內容漂移。Java 與 TypeScript 仿照 `DATASET_YEARS` 持有字面副本,
由 `test_caveat_contract.py` 釘在一起。

連帶效果(要先知道):

- `CAVEAT_QS_STALE` 是從 `DATASET_COVERAGE["QS"]` 渲染的,會變成
  "QS ranking data is a point-in-time snapshot of the 2016, 2018, 2019, 2020, 2022, 2023, 2024, 2025 and 2026 published tables."
  對封存年份,「published tables」讀起來像我們直接取得,所以需要 3.2 的補充句,
  不能只靠這一句。
- QS 2015、2017、2021 不在表內,`edition_source_coverage_caveat` 會正確指出 QS 在這些年份缺席。

### 3.2 新增一種 caveat:封存年份(只用於 `DATASET_ARCHIVE_EDITIONS` 內的組合)

建議措辭(英文,因為使用者看到的是英文 caveat):

> QS {year} ranks were recovered from an Internet Archive capture of QS's own data file taken
> on {captured}, not crawled from QS directly, and QS may have revised the table since. QS
> prints most ranks as ties or bands; the rank shown here is the lower bound of the printed
> rank, so it is not comparable position by position with the QS ranks of {live_editions}.
> Any composite or confidence that includes it inherits that imprecision.

- `{live_editions}` 是同一來源非封存的年份(目前 2025 和 2026),從兩張表相減算出,不手寫。
- 只掛在封存年份的回應上,不放進 `STANDARD_CAVEATS`。
- 照現有規則:`{...}` 用字串替換,不用 `str.format`,三種語言才不會對跳脫字元有歧見。
- 四份副本:`core/caveats.py`、`AnalyticsService.java`(常數與渲染)、`caveatMessages.ts`、
  `docs/analytics/ANALYTICS_EXPLAINABILITY.md`(含渲染規則的範例列),並讓
  `test_caveat_contract.py`、`AnalyticsCaveatContractTest` 與前端的 `snapshotCaveat.test.ts` 一起檢查。

### 3.3 名次本身要不要在回應中帶 `rank_display`

不帶的話,「rank 是下界」只存在於 caveat 文字,機器讀取的使用者(agent、前端)拿到的
`QS: 201` 看起來就是第 201 名。我建議**第二階段**讓來源排名的回應帶上 `rank_display`
(資料庫的 `ranking_record.metadata.rank_display` 已有),但這會動 Java DTO 與前端,
不屬於這次的最小範圍,見方案 B。

## 4. 方案

| 方案 | 內容 | 結果 |
|---|---|---|
| **A(建議)** | 3.1 + 3.2。範圍:覆蓋表、封存 caveat 與其四份副本、測試。 | 消除 §1 的假陳述;封存性質有揭露;名次語意只在文字裡說明。 |
| B | A + 回應帶 `rank_display` / `rank_basis`,前端顯示區間。 | 機器可讀;改動大。 |
| C | 還原:把 QS 歷年與 THE 歷年從資料庫移除(有備份),資料檔留在 repo。 | 最保守,但等於放棄這次補資料的成果。 |

我建議 **A,B 排在後面**。A 也解決 THE 2015–2024 的同一個矛盾。

## 5. 實作 A 的步驟與驗證

1. 改 `DATASET_COVERAGE`、新增 `DATASET_ARCHIVE_EDITIONS` 與 caveat 渲染(Python)。
2. 同步 Java(`DatasetScope`、`AnalyticsService`)、TypeScript(`datasetScope.ts`、`caveatMessages.ts`)、文件。
3. 新測試:封存常數對 manifest 與收據;`snapshot_caveat` 對封存年份拒絕只說「published tables」;
   `editionCaveats(2024)` 同時含封存 caveat 與 THE/ARWU partial、不再說「ARWU only」;
   2015、2017、2021 對 QS 仍說缺席。
4. 跑 `test_caveat_contract.py`、完整 Python 測試、`./mvnw -q compile` 與 Java 測試、前端 `npm test`。
5. **啟動 API,對 2016、2024 與 2026 各打一次,看實際回應的 caveats,** 再宣稱完成。
   (這一步我之前都只讀程式碼推論,沒有做過。)

## 6. 需要你決定的事

1. 方案 A / B / C?(我建議 A)
2. 封存 caveat 的措辭是否可接受?特別是最後一句「composite or confidence … inherits that imprecision」
   要不要保留。
3. 這次發布是否一併包含 THE 2015–2024?(我建議是,它們已經在資料庫,而且需要同樣的修正。)
4. QS 的 `DATASET_ARCHIVE_EDITIONS` 日期要用「資料檔快照日期」(如上)。
   這與「edition 發布日期」不同,要不要在 caveat 裡同時寫發布年份?

## 7. 實作時的偏離(2026-10-03)

1. **措辭微調。** 「prints most ranks as ties or bands」改成「prints many ranks as bands (for example 201-210)」,
   並補上「… which are stored as one position per university」。原句把並列(`=196`,名次本身是精確的)
   也算進不精確,而且「most」對 2019 年(約 49% 是區間)略為誇大。
2. **改了既有的「edition 缺哪些來源」句子。** 原句結尾「rests on one source rather than on agreement
   between several」對 2015、2017、2021 不再成立(現在有 THE 與 ARWU 兩個來源)。改為
   「rests on fewer sources than an edition that holds all of them」,四份副本與文件同步。
3. **release 層級的 QS snapshot 句子改以「live 年份」渲染。** `CAVEAT_QS_STALE` 仍是
   「…snapshot of the 2025 and 2026 published tables」,字串與先前完全相同;封存年份由各自的 caveat 說明。

實作中抓到一個實際的 bug:TypeScript 的 `String.replace` 用字串樣式只換第一個 `{source}`,而模板裡有多個,
前端會殘留未替換的 `{source}`。已改為全部替換,並在 Python、Java、TypeScript 三套測試裡釘同一個黃金字串。

驗證:Python 全套(808)、Java 全套(257)、前端 jest(373)通過;另外實際啟動 API,對 2016、2017、2024、2026
各打 `/api/v1/recommendations/explain`,確認 caveat 如上。已知範圍:`/api/v1/analytics/*` 釘在預設年份(2026),
不隨 `year` 變動,所以不會出現封存年份;`/api/v1/rankings?year=` 的清單回應沒有 `caveats` 欄位
(網頁由前端的 `editionCaveats(year)` 補上,我沒有實際檢視網頁渲染)。
