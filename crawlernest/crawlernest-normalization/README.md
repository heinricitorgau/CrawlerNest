# crawlernest-normalization

大學排名資料的正規化引擎，用於將爬蟲產出的 CSV 標準化為統一的大學名稱、國家名稱與數值分數格式。

## 研究問題

> **在不修改下游分析邏輯的前提下，如何將異質性爬蟲輸出（多種大學名稱格式、排名區間字串、不一致的國家縮寫）轉換為可直接比較的數值紀錄？**

## 模組結構

| 路徑 | 角色 |
|------|------|
| `c_engine/src/` | 核心正規化邏輯實作（C 語言）|
| `c_engine/include/` | 公開介面標頭檔 |
| `c_engine/Makefile` | 編譯腳本 |
| `c_engine/data/samples/` | 原始與正規化後的 CSV 樣本 |
| `c_engine/docs/architecture.md` | 模組架構與設計說明 |

**設計選擇**：以 C 實作核心引擎，而非使用 Python/pandas，rationale 是在大量 CSV 批次處理時維持低記憶體佔用與可預期的執行時間，同時避免引入 Python 執行期依賴。

## 在其他電腦上免安裝執行（可攜式版本）

若要在**未安裝任何開發工具**的 Windows 10 / 11 電腦（例如展示用電腦）直接執行，
不需要在該電腦安裝 gcc、make 或 MSYS2，只要產生一份可攜式套件並複製過去即可。

### 產生可攜式套件

在開發機（已安裝 MSYS2 gcc）的 `c_engine` 目錄下執行：

```powershell
.\make_dist.ps1
```

會在 `c_engine/dist/` 下產生：

- `ClawerNormalizer-Portable/` — 可攜式資料夾
- `ClawerNormalizer-Portable.zip` — 同內容壓縮檔

套件結構：

```
ClawerNormalizer-Portable/
├── clawer_normalizer.exe   靜態編譯（gcc -static），零外部 DLL 依賴
├── test_normalizer.exe     單元測試（17 / 17）
├── Run-執行.bat            雙擊啟動主程式
├── Test-測試.bat           雙擊執行單元測試
├── README.txt              使用說明
└── data/samples/           範例輸入與輸出
```

### 在目標電腦使用

1. 將整個 `ClawerNormalizer-Portable` 資料夾（或解壓後的 zip）複製到目標電腦。
2. **雙擊 `Run-執行.bat`** 即可啟動 — 啟動器會自動切換到正確目錄，相對路徑不會出錯。
3. 依選單輸入 `1` → `2` → `3` 完成載入、正規化、匯出並離開。

> **技術重點**：執行檔以 `gcc -static` 編譯，僅依賴 Windows 內建系統元件
> （`KERNEL32` 與 UCRT），不需要任何 MinGW / MSYS2 執行期 DLL，
> 因此可在任何 Windows 10 / 11 直接執行。
>
> **注意**：若目標電腦開啟「智慧型應用程式控制 (Smart App Control)」，
> 未簽章的執行檔可能被封鎖；如遇此情況請於該電腦的
> 「Windows 安全性 → 應用程式與瀏覽器控制」中關閉該功能。

## 使用說明（C 引擎，開發機）

### 1. 編譯引擎

**macOS / Linux（有 make）：**

```bash
cd c_engine
make
```

**Windows（無 make，使用 MSYS2 gcc）：**

```powershell
cd c_engine
.\build.ps1
```

或直接使用 gcc：

```powershell
gcc -Wall -Wextra -std=c11 -Iinclude src/main.c src/normalizer.c src/csv_reader.c src/csv_writer.c src/name_normalizer.c src/country_normalizer.c src/rank_parser.c src/score_parser.c src/requirement_parser.c src/utils.c -o build/clawer_normalizer.exe
```

> 編譯時會一併清空 `data/samples/normalized_universities.csv`（上一次的正規化輸出），避免誤用舊結果；`make all` 與 `build.ps1` 皆內建此行為（直接用 gcc 指令則不會清空）。

> 若想直接使用 `make`，可在 MSYS2 終端機執行 `pacman -S make`，之後於 MSYS2 UCRT64 shell 中照常使用 `make run` / `make test`。

### 2. 準備輸入資料

將爬蟲產出的 CSV 放入範例資料目錄：

```bash
cp ../../universities_world.csv data/samples/raw_universities.csv
```

輸入 CSV 須包含以下欄位（欄位順序與名稱須符合）：

```
QS Rank,University,Country,GMAT,GRE,GPA,IELTS,TOEFL,Duolingo,Overall Score,URL
```

### 3. 執行正規化

**macOS / Linux：**

```bash
make run
```

**Windows：**

```powershell
.\build\clawer_normalizer.exe
```

選單操作序列（各選項為同步複合動作）：

| 步驟 | 選單選項 | 動作 |
|------|---------|------|
| 1 | `1` | 載入 CSV 資料並顯示原始資料 |
| 2 | `2` | 執行完整正規化流程並顯示結果 |
| 3 | `3` | 匯出結果為 `.csv` 檔並自動離開程式 |

（選項 `0` 可隨時離開程式，不匯出）

### 4. 查看結果

正規化後的輸出預設儲存於：

```
data/samples/normalized_universities.csv
```

輸出格式：

```csv
University,Country,Rank Min,Rank Max,Overall Score
University of California Berkeley (Ucb),United States,12,14,91.70
```

## 驗證流程

### 單元測試

**macOS / Linux：**

```bash
cd c_engine
make test
```

**Windows：**

```powershell
cd c_engine
gcc -Wall -Wextra -std=c11 -Iinclude src/normalizer.c src/csv_reader.c src/csv_writer.c src/name_normalizer.c src/country_normalizer.c src/rank_parser.c src/score_parser.c src/requirement_parser.c src/utils.c src/tests/test_normalizer.c -o build/test_normalizer.exe
.\build\test_normalizer.exe
```

預期結果：

```
Passed: 17 / 17
All tests passed.
```

單元測試涵蓋的驗證範圍：

| 測試類別 | 驗證內容 |
|---------|---------|
| 大學名稱正規化 | 移除標點、轉小寫、壓縮空白 |
| 國家名稱正規化 | 縮寫展開（如 `U.S.A.` → `United States`）|
| 排名區間解析 | `53`、`101-150`、`Top 100` 等格式 |
| 分數解析 | 數字字串提取、無效值標記為 `-1` |
| CSV 讀寫與 escaping | 欄位分隔、引號處理 |

### 互動式整體測試

確認輸入檔存在：

```bash
ls data/samples/raw_universities.csv
```

再執行 `make run`，依序輸入：`1`、`2`、`3`（匯出後自動離開）。

### 一鍵快速驗證

```bash
printf '1\n2\n3\n' | ./build/clawer_normalizer
```

若尚未編譯，先執行 `make`。

> Windows 注意：此指令請在 Git Bash 中執行（exe 為 `./build/clawer_normalizer.exe`）。PowerShell 以管線餵入字串會附加 BOM 導致 `scanf` 讀取失敗，請改用 Git Bash 或手動輸入選項。

### 檢查輸出

```bash
sed -n '1,20p' data/samples/normalized_universities.csv
```

## 常見問題

| 問題 | 原因與處理方式 |
|------|--------------|
| `make test` 失敗 | 先執行 `make clean && make test` 重新編譯 |
| Windows 出現 `無法辨識 'make'` | 系統未安裝 make；改用上方 gcc 指令直接編譯，或在 MSYS2 安裝 make |
| Windows 主控台中文顯示亂碼 | 舊版執行檔未切換 UTF-8 主控台編碼；重新編譯即可（`main.c` 已內建 `SetConsoleOutputCP(CP_UTF8)`）|
| 重新編譯出現 `Permission denied` | 執行檔仍在執行中鎖住檔案；先結束程式（選單輸入 `0`）再編譯 |
| `載入失敗，請確認 CSV 檔案是否存在` | 確認 `data/samples/raw_universities.csv` 路徑正確；Windows 下請在 `c_engine` 目錄執行 exe（程式使用相對路徑）|
| CSV header 欄位數或欄名不符合預期 | reader 會拒絕載入；確認輸入 CSV 格式符合 11 欄規格 |
| 使用自訂資料 | 將 CSV 覆蓋至 `data/samples/raw_universities.csv` 後重新執行 |

## 開放問題

- 目前 `MAX_FIELDS = 11` 為硬編碼常數；若上游爬蟲增加欄位，reader 是否能優雅降級，還是需要修改常數？
- 國家名稱對照表目前是靜態的；當新的縮寫出現時，更新流程是否有可維護的機制？
- score parser 將無效分數標記為 `-1`；下游分析是否對此有明確的處理規則，還是依賴 writer 層的空值轉換？

## License

This project is licensed under the Apache License 2.0.
