# CrawlerNest Java 後端測試指南

本指南說明如何執行 Java 後端服務的測試，以及其背後的測試原理。

---

## 1. 測試原理與方法

我們的測試策略採用分層方法：

### A. 單元測試 (Unit Testing - JUnit 5 + Mockito)
- **方法**：專注於測試單個組件（例如 `UniversityService`）的獨立性。
- **原理**：使用 **Mocks**（透過 Mockito）來模擬相依項（如 Repository）。這讓我們可以在不需要真實資料庫或網路連接的情況下，測試業務邏輯。
- **目標**：確保每個類的內部邏輯運作正確。

### B. 集成與 API 測試 (Integration & API Testing - Python + Pytest)
- **方法**：向運行中的服務發送真實的 HTTP 請求，並驗證其回應。
- **原理**：將系統視為「黑箱」，驗證端點（Endpoints）是否可存取，且返回的 JSON 格式是否正確。
- **目標**：確保所有組件協同工作，且 API 符合客戶端預期。

---

## 2. Java 單元測試 (JUnit 5)

我們使用 JUnit 5 和 Mockito 進行單元測試。

### 前提條件
- **Java 17+**（本專案透過實驗性標記支援 **Java 25**）。
- **Maven**（建議使用隨附的 `./mvnw` 封裝器）。

### 執行測試
```bash
cd servise_for_java
./mvnw test
```

### 配置 (Java 25)
由於目前使用的是 Java 25，`pom.xml` 中包含了 `maven-surefire-plugin` 的特殊配置以支援 Byte Buddy：
```xml
<argLine>-Dnet.bytebuddy.experimental=true</argLine>
```

---

## 3. API 集成測試 (Python / Pytest)

這些測試從外部驗證 API 端點。

### 前提條件
- Python 3.9+
- `pytest` 與 `requests`（請透過 `pip install pytest requests` 安裝）

### 執行測試
1. **啟動 Java 服務**：
   ```bash
   cd servise_for_java
   ./mvnw spring-boot:run
   ```

2. **執行 Pytest**（在另一個終端機）：
   ```bash
   cd crawlernest-tests
   pytest test_ranking_api.py -v
   ```

---

## 4. 進階測試方法

為了建立更穩健的平台，我們可以使用以下進階測試方法：

### A. Controller 切片測試 (`@WebMvcTest`)
- **用途**：僅測試 Web 層（路徑映射、序列化、回應狀態），而不載入整個應用程式上下文。
- **執行**：
  ```bash
  cd servise_for_java
  ./mvnw test -Dtest=UniversityControllerTest
  ```
- **優點**：比完整的集成測試更快，但比簡單的 REST API 單元測試更全面。

### B. 性能與壓力測試 (Python)
- **用途**：驗證 API 處理併發請求的能力，並識別延遲瓶頸。
- **執行**：
  ```bash
  cd crawlernest-tests
  python3 performance_test.py
  ```
- **優點**：確保 API 可以擴展以支援多個使用者。

### C. 未來潛在測試
- **資料庫整合**：使用真實的 SQLite 資料庫進行測試（待完全實作後）。
- **端到端 (E2E)**：測試從資料爬取到 API 輸出的完整流程。

---

## 5. 專案結構說明

Java 原始碼已整合至 `servise_for_java/src/main/java/clawer` 中，以遵循標準的 Maven 結構，實現自動化編譯與測試。
