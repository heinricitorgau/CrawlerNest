# crawlernest-normalization

數據規規化引擎，用於標準化大學名稱、國家及成績分數。

## 模組說明
- **c_engine**: 使用 C 語言編寫的高效能規規化引擎。
  - `src/`: 核心實作代碼。
  - `include/`: 標頭檔。
  - `Makefile`: 編譯腳本。
  - `data/samples/`: 存放原始與規規化後的 CSV 檔案。

## 使用說明 (C 引擎)

此模組提供高效能的 CLI 工具，用於批次處理爬蟲產出的 CSV 數據。

### 1. 編譯引擎
在 `c_engine` 目錄下執行以下指令：
```bash
cd c_engine
make
```

### 2. 準備數據
將爬蟲產出的 CSV 檔案（例如 `universities_world.csv`）複製到範例數據目錄：
```bash
cp ../../universities_world.csv data/samples/raw_universities.csv
```

### 3. 執行規規化
執行編譯好的程式並按照選單操作：
```bash
make run
```
**選單操作步驟：**
1.  輸入 `1`：載入 CSV 資料。
2.  輸入 `3`：執行完整正規化流程（清洗名稱、解析排名區間、提取分數）。
3.  輸入 `4`：預覽規規化後的結果。
4.  輸入 `5`：將結果匯出成新的 `.csv` 檔。

### 4. 查看結果
規規化後的檔案預設儲存在：
`data/samples/normalized_universities.csv`

---
*註：規規化流程會移除多餘標點符號、統一轉換小寫，並將排名區間（如 101-150）解析為數值格式。*
