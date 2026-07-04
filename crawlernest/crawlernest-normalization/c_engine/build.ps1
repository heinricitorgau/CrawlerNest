# build.ps1 — Windows 建置腳本（等同 make all）
# 編譯主程式，並清空上一次的正規化輸出，避免拿到舊結果。
# 用法：在 c_engine 目錄下執行  .\build.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

gcc -Wall -Wextra -std=c11 -static -Iinclude `
    src/main.c src/normalizer.c src/csv_reader.c src/csv_writer.c `
    src/name_normalizer.c src/country_normalizer.c src/rank_parser.c `
    src/score_parser.c src/requirement_parser.c src/utils.c `
    -o build/clawer_normalizer.exe

if ($LASTEXITCODE -ne 0) {
    Write-Output "編譯失敗。"
    exit 1
}

$outputCsv = "data/samples/normalized_universities.csv"
Set-Content -Path $outputCsv -Value $null -NoNewline
Write-Output "編譯完成：build/clawer_normalizer.exe"
Write-Output "已清空 $outputCsv"
