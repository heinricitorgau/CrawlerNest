/*
 * test_regression3.c
 *
 * 第三輪弱點驅動回歸測試
 * 測試日期：2026-04-15
 * 目的：針對 Session 3 深度分析發現的四類弱點進行系統性驗證
 *
 * 弱點分類：
 *   E. country_normalizer — 含連字號國家名稱處理錯誤
 *      （如 "Timor-Leste" → 舊行為 "Timorleste"，修正後應 → "Timor-Leste"）
 *   F. utils.c to_title_case — 小寫連接詞清單不完整
 *      （原僅支援 "of"，修正後支援 and/the/for/in/at/to/by/a/an）
 *   G. name_normalizer — "Tech" 誤展開為 "Technology"
 *      （修正後 "Tech" 保留原字，不替換）
 *   H. csv_writer — rank 未解析時輸出 "-1,-1"，欄位數不對
 *      （修正後 rank_min < 0 時輸出空欄位，保持 5 欄格式）
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "normalizer.h"
#include "record.h"
#include "csv_reader.h"
#include "csv_writer.h"

/* ------------------------------------------------------------------ */
/*  測試框架                                                            */
/* ------------------------------------------------------------------ */

static int g_run  = 0;
static int g_pass = 0;
static int g_fail = 0;

static void chk(const char *label, int ok,
                const char *actual, const char *expected)
{
    g_run++;
    if (ok) {
        g_pass++;
        printf("[通過] %s\n", label);
    } else {
        g_fail++;
        printf("[失敗] %s\n", label);
        if (actual && expected)
            printf("       預期：\"%s\"\n       實際：\"%s\"\n",
                   expected, actual);
    }
}

/* ------------------------------------------------------------------ */
/*  E. country_normalizer：含連字號國家名稱                              */
/* ------------------------------------------------------------------ */

static void test_e_hyphenated_countries(void)
{
    char out[COUNTRY_LEN];

    printf("\n--- E. 含連字號國家名稱 ---\n");

    /* ── 主要修正案例 ────────────────────────────────────────────── */

    normalize_country("Timor-Leste", out, COUNTRY_LEN);
    chk("E: \"Timor-Leste\" -> \"Timor-Leste\"",
        strcmp(out, "Timor-Leste") == 0, out, "Timor-Leste");

    normalize_country("timor-leste", out, COUNTRY_LEN);
    chk("E: \"timor-leste\" (全小寫) -> \"Timor-Leste\"",
        strcmp(out, "Timor-Leste") == 0, out, "Timor-Leste");

    normalize_country("East Timor", out, COUNTRY_LEN);
    chk("E: \"East Timor\" -> \"Timor-Leste\"",
        strcmp(out, "Timor-Leste") == 0, out, "Timor-Leste");

    normalize_country("east timor", out, COUNTRY_LEN);
    chk("E: \"east timor\" (全小寫) -> \"Timor-Leste\"",
        strcmp(out, "Timor-Leste") == 0, out, "Timor-Leste");

    normalize_country("Guinea-Bissau", out, COUNTRY_LEN);
    chk("E: \"Guinea-Bissau\" -> \"Guinea-Bissau\"",
        strcmp(out, "Guinea-Bissau") == 0, out, "Guinea-Bissau");

    normalize_country("guinea-bissau", out, COUNTRY_LEN);
    chk("E: \"guinea-bissau\" (全小寫) -> \"Guinea-Bissau\"",
        strcmp(out, "Guinea-Bissau") == 0, out, "Guinea-Bissau");

    normalize_country("guinea bissau", out, COUNTRY_LEN);
    chk("E: \"guinea bissau\" (無連字號) -> \"Guinea-Bissau\"",
        strcmp(out, "Guinea-Bissau") == 0, out, "Guinea-Bissau");

    /* ── 멱等性：已正規化值再輸入應相同 ────────────────────────────── */

    normalize_country("Timor-Leste", out, COUNTRY_LEN);
    chk("E/멱等: \"Timor-Leste\" 再次輸入結果不變",
        strcmp(out, "Timor-Leste") == 0, out, "Timor-Leste");

    normalize_country("Guinea-Bissau", out, COUNTRY_LEN);
    chk("E/멱等: \"Guinea-Bissau\" 再次輸入結果不變",
        strcmp(out, "Guinea-Bissau") == 0, out, "Guinea-Bissau");

    /* ── 回歸：現有無連字號國家不受影響 ───────────────────────────── */

    normalize_country("Singapore", out, COUNTRY_LEN);
    chk("E/回歸: \"Singapore\" 不受連字號修正影響",
        strcmp(out, "Singapore") == 0, out, "Singapore");

    normalize_country("United States", out, COUNTRY_LEN);
    chk("E/回歸: \"United States\" 不受影響",
        strcmp(out, "United States") == 0, out, "United States");

    normalize_country("South Korea", out, COUNTRY_LEN);
    chk("E/回歸: \"South Korea\" 不受影響",
        strcmp(out, "South Korea") == 0, out, "South Korea");
}

/* ------------------------------------------------------------------ */
/*  F. utils.c to_title_case：小寫連接詞完整性                           */
/* ------------------------------------------------------------------ */

static void test_f_title_case_connectors(void)
{
    char out[COUNTRY_LEN];

    printf("\n--- F. to_title_case 小寫連接詞完整性 ---\n");

    /*
     * 以下測試透過 normalize_country 的 fallback 路徑觸發 to_title_case。
     * 不在 mapping_table 的國家字串會走 to_title_case 路徑。
     */

    /* "and" 在非首詞時應小寫 */
    normalize_country("Islands and Territories", out, COUNTRY_LEN);
    chk("F: fallback \"Islands and Territories\" -> \"Islands and Territories\"",
        strcmp(out, "Islands and Territories") == 0, out,
        "Islands and Territories");

    normalize_country("ISLANDS AND TERRITORIES", out, COUNTRY_LEN);
    chk("F: fallback 全大寫 \"ISLANDS AND TERRITORIES\" -> \"Islands and Territories\"",
        strcmp(out, "Islands and Territories") == 0, out,
        "Islands and Territories");

    /* "the" 在非首詞時應小寫 */
    normalize_country("Republic the Pacific", out, COUNTRY_LEN);
    chk("F: fallback \"the\" 保持小寫",
        strcmp(out, "Republic the Pacific") == 0, out,
        "Republic the Pacific");

    /* "of" 在非首詞時應小寫（原已支援，不應回歸） */
    normalize_country("Federation of Science", out, COUNTRY_LEN);
    chk("F/回歸: \"of\" 保持小寫",
        strcmp(out, "Federation of Science") == 0, out,
        "Federation of Science");

    /* "in" 在非首詞時應小寫 */
    normalize_country("Academy in Europe", out, COUNTRY_LEN);
    chk("F: fallback \"in\" 保持小寫",
        strcmp(out, "Academy in Europe") == 0, out,
        "Academy in Europe");

    /* "at" 在非首詞時應小寫 */
    normalize_country("Institute at Berlin", out, COUNTRY_LEN);
    chk("F: fallback \"at\" 保持小寫",
        strcmp(out, "Institute at Berlin") == 0, out,
        "Institute at Berlin");

    /* 首詞為連接詞時應大寫 */
    normalize_country("And the Rest", out, COUNTRY_LEN);
    chk("F/邊界: 首詞 \"And\" 保持大寫",
        out[0] == 'A' && out[1] == 'n' && out[2] == 'd', out,
        "And...");

    /* 已在 mapping_table 的含 "and" 國家不應受影響 */
    normalize_country("Trinidad and Tobago", out, COUNTRY_LEN);
    chk("F/mapping: \"Trinidad and Tobago\" -> \"Trinidad and Tobago\"",
        strcmp(out, "Trinidad and Tobago") == 0, out,
        "Trinidad and Tobago");

    normalize_country("Bosnia and Herzegovina", out, COUNTRY_LEN);
    chk("F/mapping: \"Bosnia and Herzegovina\" -> \"Bosnia and Herzegovina\"",
        strcmp(out, "Bosnia and Herzegovina") == 0, out,
        "Bosnia and Herzegovina");

    normalize_country("Antigua and Barbuda", out, COUNTRY_LEN);
    chk("F/mapping: \"Antigua and Barbuda\" -> \"Antigua and Barbuda\"",
        strcmp(out, "Antigua and Barbuda") == 0, out,
        "Antigua and Barbuda");
}

/* ------------------------------------------------------------------ */
/*  G. name_normalizer："Tech" 不應展開為 "Technology"                  */
/* ------------------------------------------------------------------ */

static void test_g_tech_not_expanded(void)
{
    char out[NAME_LEN];

    printf("\n--- G. \"Tech\" 不誤展開 ---\n");

    /* ── 主要修正案例 ────────────────────────────────────────────── */

    normalize_name("Georgia Tech", out, NAME_LEN);
    chk("G: \"Georgia Tech\" -> \"Georgia Tech\"（非 \"Georgia Technology\"）",
        strcmp(out, "Georgia Tech") == 0, out, "Georgia Tech");

    normalize_name("Texas Tech University", out, NAME_LEN);
    chk("G: \"Texas Tech University\" -> \"Texas Tech University\"",
        strcmp(out, "Texas Tech University") == 0, out,
        "Texas Tech University");

    normalize_name("Virginia Tech", out, NAME_LEN);
    chk("G: \"Virginia Tech\" -> \"Virginia Tech\"",
        strcmp(out, "Virginia Tech") == 0, out, "Virginia Tech");

    normalize_name("Cal Poly Tech", out, NAME_LEN);
    chk("G: \"Cal Poly Tech\" -> \"Cal Poly Tech\"",
        strcmp(out, "Cal Poly Tech") == 0, out, "Cal Poly Tech");

    /* 全小寫輸入 */
    normalize_name("georgia tech", out, NAME_LEN);
    chk("G: \"georgia tech\" (全小寫) -> \"Georgia Tech\"",
        strcmp(out, "Georgia Tech") == 0, out, "Georgia Tech");

    normalize_name("virginia tech", out, NAME_LEN);
    chk("G: \"virginia tech\" (全小寫) -> \"Virginia Tech\"",
        strcmp(out, "Virginia Tech") == 0, out, "Virginia Tech");

    /* 確保 "tech" 後面有更多詞時也不展開 */
    normalize_name("Tech University of Southern California", out, NAME_LEN);
    chk("G: 首詞 \"Tech\" 不展開",
        strncmp(out, "Tech", 4) == 0, out, "Tech...");

    /* ── 回歸：其他縮寫仍正確展開 ───────────────────────────────── */

    normalize_name("Univ of Tokyo", out, NAME_LEN);
    chk("G/回歸: \"Univ\" 仍展開為 \"University\"",
        strstr(out, "University") != NULL, out, "(含 University)");

    normalize_name("Inst of Science", out, NAME_LEN);
    chk("G/回歸: \"Inst\" 仍展開為 \"Institute\"",
        strstr(out, "Institute") != NULL, out, "(含 Institute)");

    /* ── 回歸：其他名稱大小寫規則不受影響 ───────────────────────── */

    normalize_name("Massachusetts Institute of Technology", out, NAME_LEN);
    chk("G/回歸: \"Massachusetts Institute of Technology\" 不受影響",
        strcmp(out, "Massachusetts Institute of Technology") == 0,
        out, "Massachusetts Institute of Technology");

    normalize_name("MIT", out, NAME_LEN);
    chk("G/回歸: \"MIT\" 仍保持全大寫",
        strcmp(out, "MIT") == 0, out, "MIT");
}

/* ------------------------------------------------------------------ */
/*  H. csv_writer：rank 未解析時輸出欄位對齊                             */
/* ------------------------------------------------------------------ */

/*
 * count_commas_in_line
 *
 * 計算一行字串中逗號的數量（不含被引號包圍的逗號）。
 * 簡化版：只計算非引號區域的逗號。
 */
static int count_commas_in_line(const char *line)
{
    int count = 0;
    int in_quotes = 0;
    size_t i;

    for (i = 0; line[i] != '\0' && line[i] != '\n'; i++) {
        if (line[i] == '"') {
            in_quotes = !in_quotes;
        } else if (line[i] == ',' && !in_quotes) {
            count++;
        }
    }
    return count;
}

static void test_h_empty_rank_fields(void)
{
    const char *filename = "build/test_r3_rank_empty.csv";
    UniversityRecord recs[3];
    FILE *fp;
    char buf[2048];
    size_t n;
    char *line;
    int line_num;

    printf("\n--- H. CSV writer：rank 未解析時欄位對齊 ---\n");

    /* 建立三筆測試資料：
     *   [0] rank 有效（正常路徑）
     *   [1] rank 無效 rank_min=-1（主要修正案例）
     *   [2] score 無效 score=-1.0
     */
    memset(recs, 0, sizeof(recs));

    /* 第 0 筆：正常資料 */
    strcpy(recs[0].normalized_name,    "Harvard University");
    strcpy(recs[0].normalized_country, "United States");
    recs[0].rank_min = 1;
    recs[0].rank_max = 1;
    recs[0].score    = 100.0;

    /* 第 1 筆：rank 未解析（rank_min = -1） */
    strcpy(recs[1].normalized_name,    "Unknown University");
    strcpy(recs[1].normalized_country, "Japan");
    recs[1].rank_min = -1;
    recs[1].rank_max = -1;
    recs[1].score    = 75.5;

    /* 第 2 筆：score 無效（score = -1.0） */
    strcpy(recs[2].normalized_name,    "No Score College");
    strcpy(recs[2].normalized_country, "Germany");
    recs[2].rank_min = 50;
    recs[2].rank_max = 100;
    recs[2].score    = -1.0;

    /* 寫出 CSV */
    chk("H: write_normalized_csv 執行成功",
        write_normalized_csv(filename, recs, 3) == 1, NULL, NULL);

    /* 讀取並驗證 */
    fp = fopen(filename, "r");
    if (!fp) {
        chk("H: 輸出 CSV 可開啟", 0, NULL, NULL);
        return;
    }

    n = fread(buf, 1, sizeof(buf) - 1, fp);
    buf[n] = '\0';
    fclose(fp);

    /* 逐行檢查逗號數（每行應有 4 個逗號 = 5 個欄位） */
    line     = buf;
    line_num = 0;
    while (*line != '\0') {
        char *end = strchr(line, '\n');
        char row[256];
        size_t row_len;
        int commas;

        if (end) {
            row_len = (size_t)(end - line);
        } else {
            row_len = strlen(line);
        }

        if (row_len == 0) {
            line = end ? end + 1 : line + strlen(line);
            continue;
        }

        if (row_len >= sizeof(row)) row_len = sizeof(row) - 1;
        memcpy(row, line, row_len);
        row[row_len] = '\0';

        commas = count_commas_in_line(row);
        {
            char label[128];
            snprintf(label, sizeof(label),
                     "H: 第 %d 行（\"%s\"）恰好有 4 個逗號（5 欄）",
                     line_num, row);
            chk(label, commas == 4, NULL, NULL);
        }

        line_num++;
        line = end ? end + 1 : line + strlen(line);
    }

    /* 驗證 rank_min=-1 的行：不應含 "-1" */
    chk("H: rank 未解析行不應含 \"-1,-1\" 字串",
        strstr(buf, "-1,-1") == NULL, buf, "(不含 -1,-1)");

    /* 驗證正常 rank 的行有正確值 */
    chk("H: 正常 rank 行含 \"1,1\"",
        strstr(buf, "1,1") != NULL, buf, "(含 1,1)");

    /* 驗證正常 score 行含 "100.00" */
    chk("H: 正常 score 行含 \"100.00\"",
        strstr(buf, "100.00") != NULL, buf, "(含 100.00)");

    /* 驗證 score=-1.0 行末尾是空（只有換行，無分數） */
    chk("H: score 無效行含 \"50,100,\"",
        strstr(buf, "50,100,") != NULL, buf, "(含 50,100,)");

    remove(filename);
}

/* ------------------------------------------------------------------ */
/*  整合測試：四類弱點修正後完整 pipeline 驗證                             */
/* ------------------------------------------------------------------ */

static void test_integration_all_fixes(void)
{
    const char *in_file  = "build/test_r3_in.csv";
    const char *out_file = "build/test_r3_out.csv";
    UniversityRecord records[10];
    int count;
    FILE *fp;
    char buf[2048];
    size_t n;

    const char *csv_content =
        "University,Country,Rank Min,Rank Max,Overall Score\n"
        "Georgia Tech,Timor-Leste,1,1,95.0\n"
        "Texas Tech University,Guinea-Bissau,2,2,88.5\n"
        "Virginia Tech,Trinidad and Tobago,,,72.0\n"
        "Univ of Tokyo,Bosnia and Herzegovina,10,10,85.0\n"
        "MIT,usa,1,1,100.0\n";

    printf("\n--- 整合：四類修正後完整 pipeline 驗證 ---\n");

    /* 寫入輸入 CSV */
    fp = fopen(in_file, "w");
    if (!fp) {
        chk("整合: 建立測試 CSV 失敗", 0, NULL, NULL);
        return;
    }
    fputs(csv_content, fp);
    fclose(fp);

    count = load_csv_data(in_file, records, 10);
    chk("整合: 五筆資料載入成功", count == 5, NULL, NULL);

    if (count != 5) { remove(in_file); return; }

    normalize_dataset(records, count);

    /* ── Fix G：Tech 不展開 ──────────────────────────────────────── */
    chk("整合/G: \"Georgia Tech\" 不展開",
        strcmp(records[0].normalized_name, "Georgia Tech") == 0,
        records[0].normalized_name, "Georgia Tech");

    chk("整合/G: \"Texas Tech University\" 不展開",
        strcmp(records[1].normalized_name, "Texas Tech University") == 0,
        records[1].normalized_name, "Texas Tech University");

    chk("整合/G: \"Virginia Tech\" 不展開",
        strcmp(records[2].normalized_name, "Virginia Tech") == 0,
        records[2].normalized_name, "Virginia Tech");

    /* ── Fix E：連字號國家 ────────────────────────────────────────── */
    chk("整合/E: \"Timor-Leste\" -> \"Timor-Leste\"",
        strcmp(records[0].normalized_country, "Timor-Leste") == 0,
        records[0].normalized_country, "Timor-Leste");

    chk("整合/E: \"Guinea-Bissau\" -> \"Guinea-Bissau\"",
        strcmp(records[1].normalized_country, "Guinea-Bissau") == 0,
        records[1].normalized_country, "Guinea-Bissau");

    /* ── Fix F：含 "and" 的國家名稱 ──────────────────────────────── */
    chk("整合/F: \"Trinidad and Tobago\" -> \"Trinidad and Tobago\"",
        strcmp(records[2].normalized_country, "Trinidad and Tobago") == 0,
        records[2].normalized_country, "Trinidad and Tobago");

    chk("整合/F: \"Bosnia and Herzegovina\" -> \"Bosnia and Herzegovina\"",
        strcmp(records[3].normalized_country, "Bosnia and Herzegovina") == 0,
        records[3].normalized_country, "Bosnia and Herzegovina");

    /* ── Fix G：Univ 展開仍正常 ─────────────────────────────────── */
    chk("整合/G/回歸: \"Univ of Tokyo\" 展開為 \"University of Tokyo\"",
        strcmp(records[3].normalized_name, "University of Tokyo") == 0,
        records[3].normalized_name, "University of Tokyo");

    /* ── 控制組 ──────────────────────────────────────────────────── */
    chk("整合/控制: \"MIT\" 保持大寫",
        strcmp(records[4].normalized_name, "MIT") == 0,
        records[4].normalized_name, "MIT");

    chk("整合/控制: \"usa\" -> \"United States\"",
        strcmp(records[4].normalized_country, "United States") == 0,
        records[4].normalized_country, "United States");

    /* ── Fix H：CSV 輸出欄位對齊 ─────────────────────────────────── */
    chk("整合/H: write_normalized_csv 執行成功",
        write_normalized_csv(out_file, records, count) == 1, NULL, NULL);

    fp = fopen(out_file, "r");
    if (fp) {
        char *line;
        int row_idx;

        n = fread(buf, 1, sizeof(buf) - 1, fp);
        buf[n] = '\0';
        fclose(fp);

        /* 每一行都應有 4 個逗號 */
        line    = buf;
        row_idx = 0;
        while (*line != '\0') {
            char *end = strchr(line, '\n');
            char row[256];
            size_t row_len;

            if (end) {
                row_len = (size_t)(end - line);
            } else {
                row_len = strlen(line);
            }

            if (row_len == 0) {
                line = end ? end + 1 : line + strlen(line);
                continue;
            }

            if (row_len >= sizeof(row)) row_len = sizeof(row) - 1;
            memcpy(row, line, row_len);
            row[row_len] = '\0';

            {
                char label[128];
                snprintf(label, sizeof(label),
                         "整合/H: 輸出第 %d 行有 4 個逗號（5 欄）", row_idx);
                chk(label, count_commas_in_line(row) == 4, NULL, NULL);
            }

            row_idx++;
            line = end ? end + 1 : line + strlen(line);
        }

        chk("整合/H: 輸出 CSV 不含 \"-1,-1\"",
            strstr(buf, "-1,-1") == NULL, buf, "(不含 -1,-1)");
    }

    remove(in_file);
    remove(out_file);
}

/* ------------------------------------------------------------------ */
/*  額外：邊界與壓力測試                                                  */
/* ------------------------------------------------------------------ */

static void test_extra_boundaries(void)
{
    char out[NAME_LEN];
    char cout[COUNTRY_LEN];

    printf("\n--- 額外：邊界與壓力測試 ---\n");

    /* NULL 輸入不崩潰 */
    normalize_name(NULL, out, NAME_LEN);
    chk("邊界: normalize_name(NULL) 不崩潰", 1, NULL, NULL);

    normalize_country(NULL, cout, COUNTRY_LEN);
    chk("邊界: normalize_country(NULL) 不崩潰", 1, NULL, NULL);

    /* 空字串 */
    normalize_name("", out, NAME_LEN);
    chk("邊界: normalize_name(\"\") 不崩潰", 1, NULL, NULL);

    normalize_country("", cout, COUNTRY_LEN);
    chk("邊界: normalize_country(\"\") 不崩潰", 1, NULL, NULL);

    /* 全空白 */
    normalize_name("   ", out, NAME_LEN);
    chk("邊界: normalize_name(\"   \") -> 空字串或修剪後為空",
        strlen(out) == 0, out, "");

    /* 僅含連字號 */
    normalize_country("-", cout, COUNTRY_LEN);
    chk("邊界: normalize_country(\"-\") 不崩潰", 1, NULL, NULL);

    /* 多個連字號 */
    normalize_country("Timor--Leste", cout, COUNTRY_LEN);
    chk("邊界: \"Timor--Leste\" (雙連字號) 不崩潰", 1, NULL, NULL);

    /* Tech 位於句首 */
    normalize_name("Tech Institute of California", out, NAME_LEN);
    chk("邊界: 首詞 \"Tech\" 不展開",
        strncmp(out, "Tech", 4) == 0, out, "Tech...");

    /* 混合大小寫 Tech */
    normalize_name("TECH University", out, NAME_LEN);
    chk("邊界: \"TECH\" 不展開（大小寫不敏感規則）",
        strstr(out, "Technology") == NULL, out, "(不含 Technology)");

    /* Univ 在句尾 */
    normalize_name("California Univ", out, NAME_LEN);
    chk("邊界: 句尾 \"Univ\" 展開為 \"University\"",
        strstr(out, "University") != NULL, out, "(含 University)");
}

/* ------------------------------------------------------------------ */
/*  main                                                               */
/* ------------------------------------------------------------------ */

int main(void)
{
    printf("╔══════════════════════════════════════════════════════╗\n");
    printf("║  第三輪弱點驅動回歸測試 — 2026-04-15                  ║\n");
    printf("╚══════════════════════════════════════════════════════╝\n");

    test_e_hyphenated_countries();
    test_f_title_case_connectors();
    test_g_tech_not_expanded();
    test_h_empty_rank_fields();
    test_integration_all_fixes();
    test_extra_boundaries();

    printf("\n╔══════════════════════════════════════════════════════╗\n");
    printf("║  測試摘要                                              ║\n");
    printf("╚══════════════════════════════════════════════════════╝\n");
    printf("通過：%d / %d\n", g_pass, g_run);
    if (g_fail > 0) {
        printf("失敗：%d 項（詳見上方輸出）\n", g_fail);
        return 1;
    }
    printf("全部測試通過。\n");
    return 0;
}
