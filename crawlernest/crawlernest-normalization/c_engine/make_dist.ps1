# make_dist.ps1 — 打包可攜式版本（免安裝，可在任何 Windows 10/11 直接執行）
# 產出：dist\ClawerNormalizer-Portable\  以及同名 .zip
# 用法：在 c_engine 目錄下執行  .\make_dist.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$gcc = "C:\msys64\ucrt64\bin\gcc.exe"
$cflags = @("-Wall", "-Wextra", "-std=c11", "-static", "-Iinclude")
$coreSrcs = @(
    "src/normalizer.c", "src/csv_reader.c", "src/csv_writer.c",
    "src/name_normalizer.c", "src/country_normalizer.c", "src/rank_parser.c",
    "src/score_parser.c", "src/requirement_parser.c", "src/utils.c"
)

Write-Output "[1/5] 以 -static 編譯主程式與測試程式..."
& $gcc @cflags ("src/main.c") @coreSrcs -o "build/clawer_normalizer.exe"
if ($LASTEXITCODE -ne 0) { Write-Output "主程式編譯失敗。"; exit 1 }
& $gcc @cflags @coreSrcs "src/tests/test_normalizer.c" -o "build/test_normalizer.exe"
if ($LASTEXITCODE -ne 0) { Write-Output "測試程式編譯失敗。"; exit 1 }

# 組裝可攜式資料夾
$distRoot = "dist"
$pkgName  = "ClawerNormalizer-Portable"
$pkg      = Join-Path $distRoot $pkgName
Write-Output "[2/5] 建立套件資料夾 $pkg ..."
if (Test-Path $pkg) { Remove-Item $pkg -Recurse -Force }
New-Item -ItemType Directory -Force (Join-Path $pkg "data/samples") | Out-Null
# 測試程式會在 build/ 下寫入暫存 CSV，預先建好此目錄
New-Item -ItemType Directory -Force (Join-Path $pkg "build") | Out-Null
Set-Content -Path (Join-Path $pkg "build/.keep") -Value "" -NoNewline

Write-Output "[3/5] 複製執行檔與範例資料..."
Copy-Item "build/clawer_normalizer.exe" $pkg
Copy-Item "build/test_normalizer.exe"   $pkg
Copy-Item "data/samples/raw_universities.csv" (Join-Path $pkg "data/samples")
# 輸出檔先放空檔（執行後才會被填入）
Set-Content -Path (Join-Path $pkg "data/samples/normalized_universities.csv") -Value $null -NoNewline

Write-Output "[4/5] 產生啟動腳本與說明..."
# 啟動器：cd 到自身目錄，讓相對路徑生效（純 ASCII，避免 .bat 編碼問題）
$runBat = @"
@echo off
cd /d "%~dp0"
clawer_normalizer.exe
echo.
echo ----------------------------------------
pause
"@
[System.IO.File]::WriteAllText((Join-Path $pkg "Run-執行.bat"), $runBat, [System.Text.Encoding]::ASCII)

$testBat = @"
@echo off
cd /d "%~dp0"
if not exist build mkdir build
test_normalizer.exe
echo.
pause
"@
[System.IO.File]::WriteAllText((Join-Path $pkg "Test-測試.bat"), $testBat, [System.Text.Encoding]::ASCII)

# README（UTF-8 BOM，Notepad 可正確顯示中文）
$readme = @"
Clawer C Data Normalization Engine — 可攜式版本 (Portable)

================================================================
如何使用
================================================================
1. 將整個 "$pkgName" 資料夾複製到目標電腦
   （任何 Windows 10 / 11 皆可，免安裝任何工具）。
2. 雙擊「Run-執行.bat」啟動程式。
3. 依選單輸入：
     1  ->  載入 CSV 並顯示原始資料
     2  ->  執行正規化並顯示結果
     3  ->  匯出結果到 CSV 並離開程式
4. 匯出的結果檔位於：
     data\samples\normalized_universities.csv

================================================================
展示單元測試
================================================================
雙擊「Test-測試.bat」可執行單元測試，顯示 17 / 17 全數通過。

================================================================
自訂輸入資料
================================================================
將你的 CSV 覆蓋到 data\samples\raw_universities.csv 後重新執行。
輸入需為 11 欄格式：
QS Rank,University,Country,GMAT,GRE,GPA,IELTS,TOEFL,Duolingo,Overall Score,URL

================================================================
技術說明
================================================================
- 執行檔以 gcc -static 編譯，不依賴任何外部 DLL 或執行期套件。
- 只使用 Windows 內建系統元件（KERNEL32、UCRT），
  可在未安裝任何開發工具的 Windows 10 / 11 電腦直接執行。
- 程式啟動時自動將主控台切換為 UTF-8，中文顯示不會亂碼。

================================================================
注意：智慧型應用程式控制 (Smart App Control)
================================================================
若目標電腦開啟了 Smart App Control，未簽章的執行檔可能被封鎖。
如遇此情況，請於該電腦關閉它：
  設定 -> 隱私權與安全性 -> Windows 安全性
  -> 應用程式與瀏覽器控制 -> 智慧型應用程式控制設定 -> 關閉
（多數教室/實驗室電腦預設為關閉，通常不受影響。）
"@
$utf8Bom = New-Object System.Text.UTF8Encoding($true)
[System.IO.File]::WriteAllText((Join-Path $pkg "README.txt"), $readme, $utf8Bom)

Write-Output "[5/5] 壓縮為 zip..."
$zip = Join-Path $distRoot "$pkgName.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path $pkg -DestinationPath $zip

Write-Output ""
Write-Output "完成！可攜式套件："
Write-Output "  資料夾: $pkg"
Write-Output "  壓縮檔: $zip"
