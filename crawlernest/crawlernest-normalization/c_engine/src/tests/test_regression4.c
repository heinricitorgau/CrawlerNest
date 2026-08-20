/*
 * test_regression4.c
 *
 * 第四輪弱點驅動回歸測試
 * 測試日期：2026-04-19
 * 目的：針對 Session 4 深度分析發現的四類弱點進行系統性驗證
 *
 * 弱點分類：
 *   I. rank_parser   — "Top"/"Rank" 前綴大小寫不敏感未完整實作
 *                      "TOP 100" / "RANK 53" 解析失敗
 *   J. country_normalizer — 別名表缺少常見資料集變體
 *                      "Korea, Rep." / "Russian Federation" / "Macao" 等
 *   K. name_normalizer / utils — 大學縮寫清單不完整
 *                      "ETH"、"UBC"、"HKUST"、"TUM"、"TU" 等降為小寫
 *   L. rank_parser   — sscanf %d 整數溢位 "9999999999" → 1410065407
 *                      （繞回正數，通過 < 0 檢查，產生非意義排名）
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
/*  I. rank_parser：大小寫不敏感前綴                                    */
/* ------------------------------------------------------------------ */

static void test_i_rank_case_insensitive(void)
{
    int mn, mx;

    printf("\n--- I. rank_parser 大小寫不敏感 ---\n");

    /* ── "TOP N" 變體 ─────────────────────────────────────────────── */
    parse_rank("TOP 100", &mn, &mx);
    chk("I: \"TOP 100\" -> 1/100",
        mn == 1 && mx == 100, NULL, NULL);

    parse_rank("Top 100", &mn, &mx);
    chk("I/回歸: \"Top 100\" -> 1/100",
        mn == 1 && mx == 100, NULL, NULL);

    parse_rank("top 100", &mn, &mx);
    chk("I/回歸: \"top 100\" -> 1/100",
        mn == 1 && mx == 100, NULL, NULL);

    parse_rank("TOP 50", &mn, &mx);
    chk("I: \"TOP 50\" -> 1/50",
        mn == 1 && mx == 50, NULL, NULL);

    parse_rank("TOP50", &mn, &mx);   /* 無空格 */
    chk("I: \"TOP50\" (無空格) -> 1/50",
        mn == 1 && mx == 50, NULL, NULL);

    /* ── "RANK N" 變體 ────────────────────────────────────────────── */
    parse_rank("RANK 53", &mn, &mx);
    chk("I: \"RANK 53\" -> 53/53",
        mn == 53 && mx == 53, NULL, NULL);

    parse_rank("Rank 53", &mn, &mx);
    chk("I/回歸: \"Rank 53\" -> 53/53",
        mn == 53 && mx == 53, NULL, NULL);

    parse_rank("rank 53", &mn, &mx);
    chk("I/回歸: \"rank 53\" -> 53/53",
        mn == 53 && mx == 53, NULL, NULL);

    parse_rank("RANK 1", &mn, &mx);
    chk("I: \"RANK 1\" -> 1/1",
        mn == 1 && mx == 1, NULL, NULL);

    /* ── 現有格式不受影響（回歸）──────────────────────────────────── */
    parse_rank("101-150", &mn, &mx);
    chk("I/回歸: 區間 \"101-150\" -> 101/150",
        mn == 101 && mx == 150, NULL, NULL);

    parse_rank("=201", &mn, &mx);
    chk("I/回歸: \"=201\" -> 201/201",
        mn == 201 && mx == 201, NULL, NULL);

    parse_rank("#10", &mn, &mx);
    chk("I/回歸: \"#10\" -> 10/10",
        mn == 10 && mx == 10, NULL, NULL);

    parse_rank("42", &mn, &mx);
    chk("I/回歸: 純數字 \"42\" -> 42/42",
        mn == 42 && mx == 42, NULL, NULL);
}

/* ------------------------------------------------------------------ */
/*  L. rank_parser：整數溢位保護                                         */
/* ------------------------------------------------------------------ */

static void test_l_rank_overflow(void)
{
    int mn, mx;

    printf("\n--- L. rank_parser 整數溢位保護 ---\n");

    /* ── 主要修正案例 ────────────────────────────────────────────── */
    parse_rank("9999999999", &mn, &mx);
    chk("L: \"9999999999\" -> -1/-1（溢位保護）",
        mn == -1 && mx == -1, NULL, NULL);

    parse_rank("2147483648", &mn, &mx);
    chk("L: \"2147483648\" (INT_MAX+1) -> -1/-1",
        mn == -1 && mx == -1, NULL, NULL);

    parse_rank("99999999999999", &mn, &mx);
    chk("L: \"99999999999999\" -> -1/-1",
        mn == -1 && mx == -1, NULL, NULL);

    /* ── 合理邊界值仍正確解析 ─────────────────────────────────────── */
    parse_rank("2000000", &mn, &mx);
    chk("L/邊界: \"2000000\" (合理大值) -> 2000000/2000000",
        mn == 2000000 && mx == 2000000, NULL, NULL);

    parse_rank("9999999", &mn, &mx);
    chk("L/邊界: \"9999999\" (MAX_REASONABLE) -> 9999999/9999999",
        mn == 9999999 && mx == 9999999, NULL, NULL);

    parse_rank("10000000", &mn, &mx);
    chk("L/邊界: \"10000000\" (超過上限) -> -1/-1",
        mn == -1 && mx == -1, NULL, NULL);

    parse_rank("1", &mn, &mx);
    chk("L/回歸: \"1\" -> 1/1",
        mn == 1 && mx == 1, NULL, NULL);

    /* ── 負數仍被拒絕 ────────────────────────────────────────────── */
    parse_rank("-1", &mn, &mx);
    chk("L/回歸: \"-1\" -> -1/-1",
        mn == -1 && mx == -1, NULL, NULL);

    parse_rank("-100", &mn, &mx);
    chk("L/回歸: \"-100\" -> -1/-1",
        mn == -1 && mx == -1, NULL, NULL);
}

/* ------------------------------------------------------------------ */
/*  J. country_normalizer：國家別名補充                                  */
/* ------------------------------------------------------------------ */

static void test_j_country_aliases(void)
{
    char out[COUNTRY_LEN];

    printf("\n--- J. country_normalizer 別名補充 ---\n");

    /* ── Korea 短形式（標點移除後）──────────────────────────────── */
    normalize_country("Korea, Rep.", out, COUNTRY_LEN);
    chk("J: \"Korea, Rep.\" -> \"South Korea\"",
        strcmp(out, "South Korea") == 0, out, "South Korea");

    normalize_country("korea rep", out, COUNTRY_LEN);
    chk("J: \"korea rep\" -> \"South Korea\"",
        strcmp(out, "South Korea") == 0, out, "South Korea");

    normalize_country("Korea, Dem. People's Rep.", out, COUNTRY_LEN);
    chk("J: \"Korea, Dem. People's Rep.\" -> \"North Korea\"",
        strcmp(out, "North Korea") == 0, out, "North Korea");

    /* ── Russia ─────────────────────────────────────────────────── */
    normalize_country("Russian Federation", out, COUNTRY_LEN);
    chk("J: \"Russian Federation\" -> \"Russia\"",
        strcmp(out, "Russia") == 0, out, "Russia");

    normalize_country("russia", out, COUNTRY_LEN);
    chk("J: \"russia\" -> \"Russia\"",
        strcmp(out, "Russia") == 0, out, "Russia");

    normalize_country("Russia", out, COUNTRY_LEN);
    chk("J/멱等: \"Russia\" -> \"Russia\"",
        strcmp(out, "Russia") == 0, out, "Russia");

    /* ── Macao / Macau ──────────────────────────────────────────── */
    normalize_country("Macao", out, COUNTRY_LEN);
    chk("J: \"Macao\" -> \"Macao SAR\"",
        strcmp(out, "Macao SAR") == 0, out, "Macao SAR");

    normalize_country("Macau", out, COUNTRY_LEN);
    chk("J: \"Macau\" -> \"Macao SAR\"",
        strcmp(out, "Macao SAR") == 0, out, "Macao SAR");

    normalize_country("macao", out, COUNTRY_LEN);
    chk("J: \"macao\" (小寫) -> \"Macao SAR\"",
        strcmp(out, "Macao SAR") == 0, out, "Macao SAR");

    /* ── Czech Republic / Czechia ────────────────────────────────── */
    normalize_country("Czech Republic", out, COUNTRY_LEN);
    chk("J: \"Czech Republic\" -> \"Czech Republic\"",
        strcmp(out, "Czech Republic") == 0, out, "Czech Republic");

    normalize_country("Czechia", out, COUNTRY_LEN);
    chk("J: \"Czechia\" -> \"Czech Republic\"",
        strcmp(out, "Czech Republic") == 0, out, "Czech Republic");

    normalize_country("czechia", out, COUNTRY_LEN);
    chk("J: \"czechia\" (小寫) -> \"Czech Republic\"",
        strcmp(out, "Czech Republic") == 0, out, "Czech Republic");

    /* ── Iran ───────────────────────────────────────────────────── */
    normalize_country("Iran", out, COUNTRY_LEN);
    chk("J: \"Iran\" -> \"Iran\"",
        strcmp(out, "Iran") == 0, out, "Iran");

    normalize_country("Islamic Republic of Iran", out, COUNTRY_LEN);
    chk("J: \"Islamic Republic of Iran\" -> \"Iran\"",
        strcmp(out, "Iran") == 0, out, "Iran");

    /* ── Vietnam ────────────────────────────────────────────────── */
    normalize_country("Viet Nam", out, COUNTRY_LEN);
    chk("J: \"Viet Nam\" -> \"Vietnam\"",
        strcmp(out, "Vietnam") == 0, out, "Vietnam");

    normalize_country("Vietnam", out, COUNTRY_LEN);
    chk("J/멱等: \"Vietnam\" -> \"Vietnam\"",
        strcmp(out, "Vietnam") == 0, out, "Vietnam");

    /* ── 回歸：現有別名不受影響 ────────────────────────────────────── */
    normalize_country("USA", out, COUNTRY_LEN);
    chk("J/回歸: \"USA\" -> \"United States\"",
        strcmp(out, "United States") == 0, out, "United States");

    normalize_country("Timor-Leste", out, COUNTRY_LEN);
    chk("J/回歸: \"Timor-Leste\" -> \"Timor-Leste\"",
        strcmp(out, "Timor-Leste") == 0, out, "Timor-Leste");

    normalize_country("South Korea", out, COUNTRY_LEN);
    chk("J/멱等: \"South Korea\" -> \"South Korea\"",
        strcmp(out, "South Korea") == 0, out, "South Korea");
}

/* ------------------------------------------------------------------ */
/*  K. name_normalizer：大學縮寫清單擴充                                  */
/* ------------------------------------------------------------------ */

static void test_k_name_acronyms(void)
{
    char out[NAME_LEN];

    printf("\n--- K. name_normalizer 縮寫清單擴充 ---\n");

    /* ── 主要修正案例 ────────────────────────────────────────────── */
    normalize_name("ETH Zurich", out, NAME_LEN);
    chk("K: \"ETH Zurich\" -> \"ETH Zurich\"",
        strcmp(out, "ETH Zurich") == 0, out, "ETH Zurich");

    normalize_name("eth zurich", out, NAME_LEN);
    chk("K: \"eth zurich\" (全小寫) -> \"ETH Zurich\"",
        strcmp(out, "ETH Zurich") == 0, out, "ETH Zurich");

    normalize_name("UBC Vancouver", out, NAME_LEN);
    chk("K: \"UBC Vancouver\" -> \"UBC Vancouver\"",
        strcmp(out, "UBC Vancouver") == 0, out, "UBC Vancouver");

    normalize_name("ubc", out, NAME_LEN);
    chk("K: \"ubc\" -> \"UBC\"",
        strcmp(out, "UBC") == 0, out, "UBC");

    normalize_name("HKUST", out, NAME_LEN);
    chk("K: \"HKUST\" -> \"HKUST\"",
        strcmp(out, "HKUST") == 0, out, "HKUST");

    normalize_name("hkust", out, NAME_LEN);
    chk("K: \"hkust\" -> \"HKUST\"",
        strcmp(out, "HKUST") == 0, out, "HKUST");

    normalize_name("TUM", out, NAME_LEN);
    chk("K: \"TUM\" -> \"TUM\"",
        strcmp(out, "TUM") == 0, out, "TUM");

    normalize_name("tum", out, NAME_LEN);
    chk("K: \"tum\" -> \"TUM\"",
        strcmp(out, "TUM") == 0, out, "TUM");

    normalize_name("TU Munich", out, NAME_LEN);
    chk("K: \"TU Munich\" -> \"TU Munich\"",
        strcmp(out, "TU Munich") == 0, out, "TU Munich");

    normalize_name("IIT Delhi", out, NAME_LEN);
    chk("K: \"IIT Delhi\" -> \"IIT Delhi\"",
        strcmp(out, "IIT Delhi") == 0, out, "IIT Delhi");

    normalize_name("RMIT University", out, NAME_LEN);
    chk("K: \"RMIT University\" -> \"RMIT University\"",
        strcmp(out, "RMIT University") == 0, out, "RMIT University");

    /* ── 멱等性 ─────────────────────────────────────────────────── */
    normalize_name("ETH Zurich", out, NAME_LEN);
    chk("K/멱等: \"ETH Zurich\" 再次輸入結果不變",
        strcmp(out, "ETH Zurich") == 0, out, "ETH Zurich");

    normalize_name("HKUST", out, NAME_LEN);
    chk("K/멱等: \"HKUST\" 再次輸入結果不變",
        strcmp(out, "HKUST") == 0, out, "HKUST");

    /* ── 回歸：現有縮寫仍正確 ─────────────────────────────────────── */
    normalize_name("MIT", out, NAME_LEN);
    chk("K/回歸: \"MIT\" 仍保持大寫",
        strcmp(out, "MIT") == 0, out, "MIT");

    normalize_name("EPFL", out, NAME_LEN);
    chk("K/回歸: \"EPFL\" 仍保持大寫",
        strcmp(out, "EPFL") == 0, out, "EPFL");

    normalize_name("KAIST", out, NAME_LEN);
    chk("K/回歸: \"KAIST\" 仍保持大寫",
        strcmp(out, "KAIST") == 0, out, "KAIST");

    normalize_name("NUS", out, NAME_LEN);
    chk("K/回歸: \"NUS\" 仍保持大寫",
        strcmp(out, "NUS") == 0, out, "NUS");

    /* ── 非縮寫仍正常 title case ──────────────────────────────────── */
    normalize_name("Oxford University", out, NAME_LEN);
    chk("K/回歸: \"Oxford University\" 正常 title case",
        strcmp(out, "Oxford University") == 0, out, "Oxford University");

    normalize_name("Georgia Tech", out, NAME_LEN);
    chk("K/回歸: \"Georgia Tech\" 不展開（Fix G 仍有效）",
        strcmp(out, "Georgia Tech") == 0, out, "Georgia Tech");
}

/* ------------------------------------------------------------------ */
/*  整合測試：四類修正後完整 pipeline 驗證                               */
/* ------------------------------------------------------------------ */

static void test_integration_s4(void)
{
    const char *in_file  = "build/test_r4_in.csv";
    const char *out_file = "build/test_r4_out.csv";
    UniversityRecord records[10];
    int count;
    FILE *fp;
    char buf[4096];
    size_t n;

    const char *csv_content =
        "University,Country,Rank Min,Rank Max,Overall Score\n"
        "ETH Zurich,Russian Federation,TOP 1,TOP 1,95.0\n"
        "HKUST,Korea Rep.,RANK 10,RANK 10,88.5\n"
        "UBC Vancouver,Czechia,TOP 50,TOP 50,82.0\n"
        "Georgia Tech,Macao,101,150,75.5\n"
        "MIT,usa,1,1,100.0\n";

    printf("\n--- 整合：Session 4 四類修正後完整 pipeline 驗證 ---\n");

    fp = fopen(in_file, "w");
    if (!fp) { chk("整合: 建立 CSV 失敗", 0, NULL, NULL); return; }
    fputs(csv_content, fp);
    fclose(fp);

    count = load_csv_data(in_file, records, 10);
    chk("整合: 五筆資料載入成功", count == 5, NULL, NULL);
    if (count != 5) { remove(in_file); return; }

    normalize_dataset(records, count);

    /* Fix K: ETH 縮寫 */
    chk("整合/K: \"ETH Zurich\" 縮寫正確",
        strcmp(records[0].normalized_name, "ETH Zurich") == 0,
        records[0].normalized_name, "ETH Zurich");

    /* Fix J: Russian Federation → Russia */
    chk("整合/J: \"Russian Federation\" -> \"Russia\"",
        strcmp(records[0].normalized_country, "Russia") == 0,
        records[0].normalized_country, "Russia");

    /* Fix I: RANK 10 → 10/10 */
    chk("整合/I: \"RANK 10\" -> 10/10",
        records[1].rank_min == 10 && records[1].rank_max == 10,
        NULL, NULL);

    /* Fix K: HKUST 縮寫 */
    chk("整合/K: \"HKUST\" 縮寫正確",
        strcmp(records[1].normalized_name, "HKUST") == 0,
        records[1].normalized_name, "HKUST");

    /* Fix J: Korea Rep. → South Korea */
    chk("整合/J: \"Korea Rep.\" -> \"South Korea\"",
        strcmp(records[1].normalized_country, "South Korea") == 0,
        records[1].normalized_country, "South Korea");

    /* Fix K: UBC 縮寫 */
    chk("整合/K: \"UBC Vancouver\" 縮寫正確",
        strcmp(records[2].normalized_name, "UBC Vancouver") == 0,
        records[2].normalized_name, "UBC Vancouver");

    /* Fix I: TOP 50 → 1/50 */
    chk("整合/I: \"TOP 50\" -> 1/50",
        records[2].rank_min == 1 && records[2].rank_max == 50,
        NULL, NULL);

    /* Fix J: Czechia → Czech Republic */
    chk("整合/J: \"Czechia\" -> \"Czech Republic\"",
        strcmp(records[2].normalized_country, "Czech Republic") == 0,
        records[2].normalized_country, "Czech Republic");

    /* Fix G 仍有效: Georgia Tech 不展開 */
    chk("整合/G/回歸: \"Georgia Tech\" 不展開",
        strcmp(records[3].normalized_name, "Georgia Tech") == 0,
        records[3].normalized_name, "Georgia Tech");

    /* Fix J: Macao → Macao SAR */
    chk("整合/J: \"Macao\" -> \"Macao SAR\"",
        strcmp(records[3].normalized_country, "Macao SAR") == 0,
        records[3].normalized_country, "Macao SAR");

    /* 控制組 */
    chk("整合/控制: \"MIT\" 保持大寫",
        strcmp(records[4].normalized_name, "MIT") == 0,
        records[4].normalized_name, "MIT");

    chk("整合/控制: \"usa\" -> \"United States\"",
        strcmp(records[4].normalized_country, "United States") == 0,
        records[4].normalized_country, "United States");

    /* CSV 輸出對齊驗證 */
    chk("整合/H/回歸: write_normalized_csv 執行成功",
        write_normalized_csv(out_file, records, count) == 1, NULL, NULL);

    fp = fopen(out_file, "r");
    if (fp) {
        n = fread(buf, 1, sizeof(buf) - 1, fp);
        buf[n] = '\0';
        fclose(fp);
        chk("整合/H/回歸: 輸出不含 \"-1,-1\"",
            strstr(buf, "-1,-1") == NULL, buf, "(不含 -1,-1)");
    }

    remove(in_file);
    remove(out_file);
}

/* ------------------------------------------------------------------ */
/*  額外：邊界與回歸補強                                                  */
/* ------------------------------------------------------------------ */

static void test_extra_boundaries(void)
{
    int mn, mx;
    char out[NAME_LEN];
    char cout[COUNTRY_LEN];

    printf("\n--- 額外：邊界與回歸補強 ---\n");

    /* rank 0 行為一致（視為有效，雖然語意上不存在） */
    parse_rank("0", &mn, &mx);
    chk("邊界: \"0\" -> 0/0（接受，行為一致）",
        mn == 0 && mx == 0, NULL, NULL);

    /* 超大值連字號格式 */
    parse_rank("9999999999-9999999999", &mn, &mx);
    chk("邊界: \"9999999999-9999999999\" -> -1/-1",
        mn == -1 && mx == -1, NULL, NULL);

    /* TOP 後跟溢位數字 */
    parse_rank("TOP 9999999999", &mn, &mx);
    chk("邊界: \"TOP 9999999999\" -> -1/-1（溢位保護）",
        mn == -1 && mx == -1, NULL, NULL);

    /* 空字串 */
    parse_rank("", &mn, &mx);
    chk("邊界/回歸: 空字串 -> -1/-1", mn == -1 && mx == -1, NULL, NULL);

    /* NULL */
    parse_rank(NULL, &mn, &mx);
    chk("邊界/回歸: NULL -> -1/-1", mn == -1 && mx == -1, NULL, NULL);

    /* 確保現有 Session 3 修正（E/F/G/H）仍有效 */
    normalize_country("Timor-Leste", cout, COUNTRY_LEN);
    chk("邊界/E回歸: \"Timor-Leste\" -> \"Timor-Leste\"",
        strcmp(cout, "Timor-Leste") == 0, cout, "Timor-Leste");

    normalize_country("Trinidad and Tobago", cout, COUNTRY_LEN);
    chk("邊界/F回歸: \"Trinidad and Tobago\" -> \"Trinidad and Tobago\"",
        strcmp(cout, "Trinidad and Tobago") == 0, cout, "Trinidad and Tobago");

    normalize_name("Virginia Tech", out, NAME_LEN);
    chk("邊界/G回歸: \"Virginia Tech\" 不展開",
        strcmp(out, "Virginia Tech") == 0, out, "Virginia Tech");

    /* 新縮寫不影響非縮寫詞 */
    normalize_name("Technical University of Denmark", out, NAME_LEN);
    chk("邊界/K: \"Technical University of Denmark\" 正常 title case",
        strcmp(out, "Technical University of Denmark") == 0,
        out, "Technical University of Denmark");

    /* 混合新舊縮寫的名稱 */
    normalize_name("ETH Zurich and MIT", out, NAME_LEN);
    chk("邊界/K: \"ETH Zurich and MIT\" 複合縮寫",
        strcmp(out, "ETH Zurich and MIT") == 0,
        out, "ETH Zurich and MIT");
}

/* ------------------------------------------------------------------ */
/*  main                                                               */
/* ------------------------------------------------------------------ */

int main(void)
{
    printf("╔══════════════════════════════════════════════════════╗\n");
    printf("║  第四輪弱點驅動回歸測試 — 2026-04-19                  ║\n");
    printf("╚══════════════════════════════════════════════════════╝\n");

    test_i_rank_case_insensitive();
    test_l_rank_overflow();
    test_j_country_aliases();
    test_k_name_acronyms();
    test_integration_s4();
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
