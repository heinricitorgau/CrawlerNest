/*
 * test_regression6.c
 *
 * 第六輪弱點驅動回歸測試
 * 測試日期：2026-04-22
 * 目的：針對 Session 6 深度探測發現的三類弱點進行系統性驗證
 *
 * 弱點分類：
 *   R. country_normalizer — 三類別名缺漏：
 *       R1. "The X" 前綴變體（"The Netherlands" / "The United States" 等）
 *           normalize_basic 將 "The Netherlands" → "the netherlands"，
 *           但別名表無此條目 → 回退 title case → "The Netherlands"（應為 "Netherlands"）
 *       R2. "PR China" / "P.R. China" 未映射至 "China (Mainland)"
 *       R3. 官方長名（"Republic of India" / "Federal Republic of Germany" 等）
 *           在 UN / World Bank 資料中常見，但未在別名表中
 *   S. score_parser — ".5" 被解析為 5.0 而非 0.5
 *       extract_first_number 遇到 '.' 時若尚未 started，跳過它；
 *       下一個字元 '5' 成為數字起點 → 結果是 5.0
 *   T. name_normalizer / utils — KAUST（阿卜杜拉國王科技大學）等縮寫缺漏
 *       "KAUST" 未在 is_name_acronym / is_acronym 清單中 → "Kaust"
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

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

#define DBL_EQ(a, b) (fabs((a) - (b)) < 1e-9)

/* ------------------------------------------------------------------ */
/*  R1. country_normalizer："The X" 前綴變體                           */
/* ------------------------------------------------------------------ */

static void test_r1_the_prefix(void)
{
    char out[COUNTRY_LEN];

    printf("\n--- R1. country_normalizer: \"The X\" 前綴變體 ---\n");

    /* 主要修正案例 */
    normalize_country("The Netherlands", out, COUNTRY_LEN);
    chk("R1: \"The Netherlands\" -> \"Netherlands\"",
        strcmp(out, "Netherlands") == 0, out, "Netherlands");

    normalize_country("The United States", out, COUNTRY_LEN);
    chk("R1: \"The United States\" -> \"United States\"",
        strcmp(out, "United States") == 0, out, "United States");

    normalize_country("The United States of America", out, COUNTRY_LEN);
    chk("R1: \"The United States of America\" -> \"United States\"",
        strcmp(out, "United States") == 0, out, "United States");

    normalize_country("The United Kingdom", out, COUNTRY_LEN);
    chk("R1: \"The United Kingdom\" -> \"United Kingdom\"",
        strcmp(out, "United Kingdom") == 0, out, "United Kingdom");

    normalize_country("The People's Republic of China", out, COUNTRY_LEN);
    chk("R1: \"The People's Republic of China\" -> \"China (Mainland)\"",
        strcmp(out, "China (Mainland)") == 0, out, "China (Mainland)");

    /* 멱等性：去掉 "The " 的版本已存在，行為不變 */
    normalize_country("Netherlands", out, COUNTRY_LEN);
    chk("R1/멱等: \"Netherlands\" -> \"Netherlands\"",
        strcmp(out, "Netherlands") == 0, out, "Netherlands");

    normalize_country("United States", out, COUNTRY_LEN);
    chk("R1/멱等: \"United States\" -> \"United States\"",
        strcmp(out, "United States") == 0, out, "United States");

    normalize_country("United Kingdom", out, COUNTRY_LEN);
    chk("R1/멱等: \"United Kingdom\" -> \"United Kingdom\"",
        strcmp(out, "United Kingdom") == 0, out, "United Kingdom");
}

/* ------------------------------------------------------------------ */
/*  R2. country_normalizer：PR China / P.R. China 別名                 */
/* ------------------------------------------------------------------ */

static void test_r2_pr_china(void)
{
    char out[COUNTRY_LEN];

    printf("\n--- R2. country_normalizer: PR China 別名 ---\n");

    normalize_country("PR China", out, COUNTRY_LEN);
    chk("R2: \"PR China\" -> \"China (Mainland)\"",
        strcmp(out, "China (Mainland)") == 0, out, "China (Mainland)");

    normalize_country("P.R. China", out, COUNTRY_LEN);
    chk("R2: \"P.R. China\" -> \"China (Mainland)\"",
        strcmp(out, "China (Mainland)") == 0, out, "China (Mainland)");

    normalize_country("P.R.C.", out, COUNTRY_LEN);
    chk("R2/回歸: \"P.R.C.\" -> \"China (Mainland)\" (via prc)",
        strcmp(out, "China (Mainland)") == 0, out, "China (Mainland)");

    normalize_country("PRC", out, COUNTRY_LEN);
    chk("R2/回歸: \"PRC\" -> \"China (Mainland)\"",
        strcmp(out, "China (Mainland)") == 0, out, "China (Mainland)");

    normalize_country("People's Republic of China", out, COUNTRY_LEN);
    chk("R2/回歸: \"People's Republic of China\" -> \"China (Mainland)\"",
        strcmp(out, "China (Mainland)") == 0, out, "China (Mainland)");

    normalize_country("China", out, COUNTRY_LEN);
    chk("R2/回歸: \"China\" -> \"China (Mainland)\"",
        strcmp(out, "China (Mainland)") == 0, out, "China (Mainland)");
}

/* ------------------------------------------------------------------ */
/*  R3. country_normalizer：官方長名別名                               */
/* ------------------------------------------------------------------ */

static void test_r3_official_names(void)
{
    char out[COUNTRY_LEN];

    printf("\n--- R3. country_normalizer: 官方長名別名 ---\n");

    normalize_country("Republic of India", out, COUNTRY_LEN);
    chk("R3: \"Republic of India\" -> \"India\"",
        strcmp(out, "India") == 0, out, "India");

    normalize_country("Federal Republic of Germany", out, COUNTRY_LEN);
    chk("R3: \"Federal Republic of Germany\" -> \"Germany\"",
        strcmp(out, "Germany") == 0, out, "Germany");

    normalize_country("Kingdom of Saudi Arabia", out, COUNTRY_LEN);
    chk("R3: \"Kingdom of Saudi Arabia\" -> \"Saudi Arabia\"",
        strcmp(out, "Saudi Arabia") == 0, out, "Saudi Arabia");

    normalize_country("Swiss Confederation", out, COUNTRY_LEN);
    chk("R3: \"Swiss Confederation\" -> \"Switzerland\"",
        strcmp(out, "Switzerland") == 0, out, "Switzerland");

    normalize_country("Hellenic Republic", out, COUNTRY_LEN);
    chk("R3: \"Hellenic Republic\" -> \"Greece\"",
        strcmp(out, "Greece") == 0, out, "Greece");

    normalize_country("Republic of South Africa", out, COUNTRY_LEN);
    chk("R3: \"Republic of South Africa\" -> \"South Africa\"",
        strcmp(out, "South Africa") == 0, out, "South Africa");

    normalize_country("Kingdom of the Netherlands", out, COUNTRY_LEN);
    chk("R3: \"Kingdom of the Netherlands\" -> \"Netherlands\"",
        strcmp(out, "Netherlands") == 0, out, "Netherlands");

    normalize_country("Islamic Republic of Pakistan", out, COUNTRY_LEN);
    chk("R3: \"Islamic Republic of Pakistan\" -> \"Pakistan\"",
        strcmp(out, "Pakistan") == 0, out, "Pakistan");

    normalize_country("Federative Republic of Brazil", out, COUNTRY_LEN);
    chk("R3: \"Federative Republic of Brazil\" -> \"Brazil\"",
        strcmp(out, "Brazil") == 0, out, "Brazil");

    normalize_country("Republic of Italy", out, COUNTRY_LEN);
    chk("R3: \"Republic of Italy\" -> \"Italy\"",
        strcmp(out, "Italy") == 0, out, "Italy");

    normalize_country("Kingdom of Spain", out, COUNTRY_LEN);
    chk("R3: \"Kingdom of Spain\" -> \"Spain\"",
        strcmp(out, "Spain") == 0, out, "Spain");

    normalize_country("Kingdom of Norway", out, COUNTRY_LEN);
    chk("R3: \"Kingdom of Norway\" -> \"Norway\"",
        strcmp(out, "Norway") == 0, out, "Norway");

    normalize_country("Kingdom of Sweden", out, COUNTRY_LEN);
    chk("R3: \"Kingdom of Sweden\" -> \"Sweden\"",
        strcmp(out, "Sweden") == 0, out, "Sweden");

    normalize_country("Kingdom of Denmark", out, COUNTRY_LEN);
    chk("R3: \"Kingdom of Denmark\" -> \"Denmark\"",
        strcmp(out, "Denmark") == 0, out, "Denmark");

    normalize_country("Republic of Austria", out, COUNTRY_LEN);
    chk("R3: \"Republic of Austria\" -> \"Austria\"",
        strcmp(out, "Austria") == 0, out, "Austria");

    normalize_country("Republic of Ireland", out, COUNTRY_LEN);
    chk("R3: \"Republic of Ireland\" -> \"Ireland\"",
        strcmp(out, "Ireland") == 0, out, "Ireland");

    normalize_country("Republic of Poland", out, COUNTRY_LEN);
    chk("R3: \"Republic of Poland\" -> \"Poland\"",
        strcmp(out, "Poland") == 0, out, "Poland");

    normalize_country("Republic of Portugal", out, COUNTRY_LEN);
    chk("R3: \"Republic of Portugal\" -> \"Portugal\"",
        strcmp(out, "Portugal") == 0, out, "Portugal");

    normalize_country("Republic of Finland", out, COUNTRY_LEN);
    chk("R3: \"Republic of Finland\" -> \"Finland\"",
        strcmp(out, "Finland") == 0, out, "Finland");

    normalize_country("Kingdom of Belgium", out, COUNTRY_LEN);
    chk("R3: \"Kingdom of Belgium\" -> \"Belgium\"",
        strcmp(out, "Belgium") == 0, out, "Belgium");

    /* 멱等性：短名稱本身也正確 */
    normalize_country("India", out, COUNTRY_LEN);
    chk("R3/멱等: \"India\" -> \"India\"",
        strcmp(out, "India") == 0, out, "India");

    normalize_country("Germany", out, COUNTRY_LEN);
    chk("R3/멱等: \"Germany\" -> \"Germany\"",
        strcmp(out, "Germany") == 0, out, "Germany");

    /* 回歸：Session 4 已有的別名不受影響 */
    normalize_country("Russia", out, COUNTRY_LEN);
    chk("R3/回歸: \"Russia\" -> \"Russia\"",
        strcmp(out, "Russia") == 0, out, "Russia");

    normalize_country("Czechia", out, COUNTRY_LEN);
    chk("R3/回歸: \"Czechia\" -> \"Czech Republic\"",
        strcmp(out, "Czech Republic") == 0, out, "Czech Republic");

    normalize_country("Vietnam", out, COUNTRY_LEN);
    chk("R3/回歸: \"Vietnam\" -> \"Vietnam\"",
        strcmp(out, "Vietnam") == 0, out, "Vietnam");
}

/* ------------------------------------------------------------------ */
/*  S. score_parser：前導小數點修正                                    */
/* ------------------------------------------------------------------ */

static void test_s_score_leading_dot(void)
{
    double sc;

    printf("\n--- S. score_parser: 前導小數點修正 ---\n");

    /* 主要修正案例 */
    sc = parse_score(".5");
    chk("S: \".5\" -> 0.5",
        DBL_EQ(sc, 0.5), NULL, NULL);

    sc = parse_score(".75");
    chk("S: \".75\" -> 0.75",
        DBL_EQ(sc, 0.75), NULL, NULL);

    sc = parse_score(".123");
    chk("S: \".123\" -> 0.123",
        DBL_EQ(sc, 0.123), NULL, NULL);

    /* 孤立小數點應失敗 */
    sc = parse_score(".");
    chk("S/邊界: \".\" -> -1.0（孤立小數點拒絕）",
        DBL_EQ(sc, -1.0), NULL, NULL);

    /* 回歸：現有格式不受影響 */
    sc = parse_score("98.4");
    chk("S/回歸: \"98.4\" -> 98.4",
        DBL_EQ(sc, 98.4), NULL, NULL);

    sc = parse_score("0");
    chk("S/回歸: \"0\" -> 0.0",
        DBL_EQ(sc, 0.0), NULL, NULL);

    sc = parse_score("100.0");
    chk("S/回歸: \"100.0\" -> 100.0",
        DBL_EQ(sc, 100.0), NULL, NULL);

    sc = parse_score("+50.5");
    chk("S/回歸: \"+50.5\" -> 50.5",
        DBL_EQ(sc, 50.5), NULL, NULL);

    sc = parse_score("Score: 91.25");
    chk("S/回歸: \"Score: 91.25\" -> 91.25",
        DBL_EQ(sc, 91.25), NULL, NULL);

    sc = parse_score("abc");
    chk("S/回歸: \"abc\" -> -1.0（無數字）",
        DBL_EQ(sc, -1.0), NULL, NULL);

    sc = parse_score("");
    chk("S/回歸: 空字串 -> -1.0",
        DBL_EQ(sc, -1.0), NULL, NULL);

    sc = parse_score(NULL);
    chk("S/回歸: NULL -> -1.0",
        DBL_EQ(sc, -1.0), NULL, NULL);
}

/* ------------------------------------------------------------------ */
/*  T. name_normalizer：KAUST / HKU 縮寫                              */
/* ------------------------------------------------------------------ */

static void test_t_name_acronyms(void)
{
    char out[NAME_LEN];

    printf("\n--- T. name_normalizer: KAUST / HKU 縮寫 ---\n");

    /* 主要修正案例 */
    normalize_name("KAUST", out, NAME_LEN);
    chk("T: \"KAUST\" -> \"KAUST\"",
        strcmp(out, "KAUST") == 0, out, "KAUST");

    normalize_name("kaust", out, NAME_LEN);
    chk("T: \"kaust\" (全小寫) -> \"KAUST\"",
        strcmp(out, "KAUST") == 0, out, "KAUST");

    normalize_name("KAUST University", out, NAME_LEN);
    chk("T: \"KAUST University\" -> \"KAUST University\"",
        strcmp(out, "KAUST University") == 0, out, "KAUST University");

    normalize_name("HKU", out, NAME_LEN);
    chk("T: \"HKU\" -> \"HKU\"",
        strcmp(out, "HKU") == 0, out, "HKU");

    normalize_name("hku", out, NAME_LEN);
    chk("T: \"hku\" (全小寫) -> \"HKU\"",
        strcmp(out, "HKU") == 0, out, "HKU");

    normalize_name("The University of Hong Kong (HKU)", out, NAME_LEN);
    chk("T: \"The University of Hong Kong (HKU)\" -> correct title case",
        strcmp(out, "The University of Hong Kong (HKU)") == 0,
        out, "The University of Hong Kong (HKU)");

    /* 멱等性 */
    normalize_name("KAUST", out, NAME_LEN);
    chk("T/멱等: \"KAUST\" 再次輸入不變",
        strcmp(out, "KAUST") == 0, out, "KAUST");

    /* 回歸：現有縮寫仍正確 */
    normalize_name("MIT", out, NAME_LEN);
    chk("T/回歸: \"MIT\" -> \"MIT\"",
        strcmp(out, "MIT") == 0, out, "MIT");

    normalize_name("ETH Zurich", out, NAME_LEN);
    chk("T/回歸: \"ETH Zurich\" -> \"ETH Zurich\"",
        strcmp(out, "ETH Zurich") == 0, out, "ETH Zurich");

    normalize_name("HKUST", out, NAME_LEN);
    chk("T/回歸: \"HKUST\" -> \"HKUST\"",
        strcmp(out, "HKUST") == 0, out, "HKUST");

    normalize_name("KAIST", out, NAME_LEN);
    chk("T/回歸: \"KAIST\" -> \"KAIST\"",
        strcmp(out, "KAIST") == 0, out, "KAIST");

    normalize_name("IIT Delhi", out, NAME_LEN);
    chk("T/回歸: \"IIT Delhi\" -> \"IIT Delhi\"",
        strcmp(out, "IIT Delhi") == 0, out, "IIT Delhi");
}

/* ------------------------------------------------------------------ */
/*  整合測試：Session 6 三類修正完整 pipeline 驗證                     */
/* ------------------------------------------------------------------ */

static void test_integration_s6(void)
{
    const char *in_file  = "build/test_r6_int_in.csv";
    const char *out_file = "build/test_r6_int_out.csv";
    UniversityRecord records[10];
    int count;
    FILE *fp;
    char buf[4096];
    size_t n;

    /*
     * CSV 設計（各行針對一個修正）：
     *  Row 0: "KAUST"            + "The Netherlands" + rank + ".5" score
     *  Row 1: "HKU"              + "PR China"        + rank + "85.0" score
     *  Row 2: "ETH Zurich"       + "Swiss Confederation" + rank + "92.3"
     *  Row 3: "MIT"              + "The United States"   + rank + "100.0"
     *  Row 4: "Georgia Tech"     + "Federal Republic of Germany" + rank + "75.5"
     */
    const char *csv_content =
        "University,Country,Rank Min,Rank Max,Overall Score\n"
        "KAUST,The Netherlands,101,150,.5\n"
        "HKU,PR China,51,100,85.0\n"
        "ETH Zurich,Swiss Confederation,1,10,92.3\n"
        "MIT,The United States,1,1,100.0\n"
        "Georgia Tech,Federal Republic of Germany,201,250,75.5\n";

    printf("\n--- 整合：Session 6 三類修正完整 pipeline 驗證 ---\n");

    fp = fopen(in_file, "w");
    if (!fp) { chk("整合: 建立 CSV 失敗", 0, NULL, NULL); return; }
    fputs(csv_content, fp);
    fclose(fp);

    count = load_csv_data(in_file, records, 10);
    chk("整合: 五筆資料載入成功", count == 5, NULL, NULL);
    if (count != 5) { remove(in_file); return; }

    normalize_dataset(records, count);

    /* Fix T: KAUST 縮寫 */
    chk("整合/T: \"KAUST\" 縮寫正確",
        strcmp(records[0].normalized_name, "KAUST") == 0,
        records[0].normalized_name, "KAUST");

    /* Fix R1: "The Netherlands" → "Netherlands" */
    chk("整合/R1: \"The Netherlands\" -> \"Netherlands\"",
        strcmp(records[0].normalized_country, "Netherlands") == 0,
        records[0].normalized_country, "Netherlands");

    /* Fix S: ".5" → 0.5 */
    chk("整合/S: score \".5\" -> 0.5",
        DBL_EQ(records[0].score, 0.5), NULL, NULL);

    /* Fix T: HKU 縮寫 */
    chk("整合/T: \"HKU\" 縮寫正確",
        strcmp(records[1].normalized_name, "HKU") == 0,
        records[1].normalized_name, "HKU");

    /* Fix R2: "PR China" → "China (Mainland)" */
    chk("整合/R2: \"PR China\" -> \"China (Mainland)\"",
        strcmp(records[1].normalized_country, "China (Mainland)") == 0,
        records[1].normalized_country, "China (Mainland)");

    /* Fix K 回歸: ETH 縮寫 */
    chk("整合/K回歸: \"ETH Zurich\" 縮寫正確",
        strcmp(records[2].normalized_name, "ETH Zurich") == 0,
        records[2].normalized_name, "ETH Zurich");

    /* Fix R3: "Swiss Confederation" → "Switzerland" */
    chk("整合/R3: \"Swiss Confederation\" -> \"Switzerland\"",
        strcmp(records[2].normalized_country, "Switzerland") == 0,
        records[2].normalized_country, "Switzerland");

    /* Fix R1: "The United States" → "United States" */
    chk("整合/R1: \"The United States\" -> \"United States\"",
        strcmp(records[3].normalized_country, "United States") == 0,
        records[3].normalized_country, "United States");

    /* Fix G 回歸: Georgia Tech 不展開 */
    chk("整合/G回歸: \"Georgia Tech\" 不展開",
        strcmp(records[4].normalized_name, "Georgia Tech") == 0,
        records[4].normalized_name, "Georgia Tech");

    /* Fix R3: "Federal Republic of Germany" → "Germany" */
    chk("整合/R3: \"Federal Republic of Germany\" -> \"Germany\"",
        strcmp(records[4].normalized_country, "Germany") == 0,
        records[4].normalized_country, "Germany");

    /* CSV 寫出驗證 */
    chk("整合/寫出: write_normalized_csv 成功",
        write_normalized_csv(out_file, records, count) == 1, NULL, NULL);

    fp = fopen(out_file, "r");
    if (fp) {
        n = fread(buf, 1, sizeof(buf) - 1, fp);
        buf[n] = '\0';
        fclose(fp);
        chk("整合/寫出: 輸出不含 \"-1,-1\"",
            strstr(buf, "-1,-1") == NULL, buf, "(不含 -1,-1)");
        chk("整合/寫出: 輸出含 \"KAUST\"",
            strstr(buf, "KAUST") != NULL, buf, "(含 KAUST)");
        chk("整合/寫出: 輸出含 \"Netherlands\"（無 \"The \"）",
            strstr(buf, "Netherlands") != NULL &&
            strstr(buf, "The Netherlands") == NULL,
            buf, "(含 Netherlands, 不含 The Netherlands)");
    }

    remove(in_file);
    remove(out_file);
}

/* ------------------------------------------------------------------ */
/*  額外：邊界與全局回歸補強                                            */
/* ------------------------------------------------------------------ */

static void test_extra_s6(void)
{
    int mn, mx;
    char cout[COUNTRY_LEN];
    char nout[NAME_LEN];
    double sc;

    printf("\n--- 額外：邊界與全局回歸補強 ---\n");

    /* country_normalizer 回歸：舊有條目不受 Fix R 影響 */
    normalize_country("usa", cout, COUNTRY_LEN);
    chk("回歸: \"usa\" -> \"United States\"",
        strcmp(cout, "United States") == 0, cout, "United States");

    normalize_country("UK", cout, COUNTRY_LEN);
    chk("回歸: \"UK\" -> \"United Kingdom\"",
        strcmp(cout, "United Kingdom") == 0, cout, "United Kingdom");

    normalize_country("South Korea", cout, COUNTRY_LEN);
    chk("回歸: \"South Korea\" -> \"South Korea\"",
        strcmp(cout, "South Korea") == 0, cout, "South Korea");

    normalize_country("Macao SAR", cout, COUNTRY_LEN);
    chk("回歸/J: \"Macao SAR\" -> \"Macao SAR\"",
        strcmp(cout, "Macao SAR") == 0, cout, "Macao SAR");

    normalize_country("Timor-Leste", cout, COUNTRY_LEN);
    chk("回歸/E: \"Timor-Leste\" -> \"Timor-Leste\"",
        strcmp(cout, "Timor-Leste") == 0, cout, "Timor-Leste");

    /* score_parser 回歸：Fix S 不影響現有解析 */
    sc = parse_score("98.4");
    chk("回歸/S: \"98.4\" -> 98.4",
        DBL_EQ(sc, 98.4), NULL, NULL);

    sc = parse_score("100");
    chk("回歸/S: \"100\" -> 100.0",
        DBL_EQ(sc, 100.0), NULL, NULL);

    /* name_normalizer 回歸：舊縮寫清單不受影響 */
    normalize_name("MIT", nout, NAME_LEN);
    chk("回歸/T: \"MIT\" -> \"MIT\"",
        strcmp(nout, "MIT") == 0, nout, "MIT");

    normalize_name("EPFL", nout, NAME_LEN);
    chk("回歸/T: \"EPFL\" -> \"EPFL\"",
        strcmp(nout, "EPFL") == 0, nout, "EPFL");

    normalize_name("UBC Vancouver", nout, NAME_LEN);
    chk("回歸/K: \"UBC Vancouver\" -> \"UBC Vancouver\"",
        strcmp(nout, "UBC Vancouver") == 0, nout, "UBC Vancouver");

    normalize_name("Georgia Tech", nout, NAME_LEN);
    chk("回歸/G: \"Georgia Tech\" 不展開",
        strcmp(nout, "Georgia Tech") == 0, nout, "Georgia Tech");

    /* rank_parser 回歸：Session 5 修正不受影響 */
    parse_rank("TOP 0", &mn, &mx);
    chk("回歸/P: \"TOP 0\" -> -1/-1",
        mn == -1 && mx == -1, NULL, NULL);

    parse_rank("150-101", &mn, &mx);
    chk("回歸/Q: \"150-101\" -> 101/150 (auto-swap)",
        mn == 101 && mx == 150, NULL, NULL);

    parse_rank("TOP 10", &mn, &mx);
    chk("回歸/I: \"TOP 10\" -> 1/10",
        mn == 1 && mx == 10, NULL, NULL);

    /* score 邊界：.0 前導小數點（整數部分為 0） */
    sc = parse_score(".0");
    chk("S/邊界: \".0\" -> 0.0",
        DBL_EQ(sc, 0.0), NULL, NULL);

    /* 多個小數點 ".5.3" → ".5" 然後 '.' 是第二個小數點，停止 → 0.5 */
    sc = parse_score(".5.3");
    chk("S/邊界: \".5.3\" -> 0.5（第二個小數點停止）",
        DBL_EQ(sc, 0.5), NULL, NULL);
}

/* ------------------------------------------------------------------ */
/*  main                                                               */
/* ------------------------------------------------------------------ */

int main(void)
{
    printf("╔══════════════════════════════════════════════════════╗\n");
    printf("║  第六輪弱點驅動回歸測試 — 2026-04-22                  ║\n");
    printf("╚══════════════════════════════════════════════════════╝\n");

    test_r1_the_prefix();
    test_r2_pr_china();
    test_r3_official_names();
    test_s_score_leading_dot();
    test_t_name_acronyms();
    test_integration_s6();
    test_extra_s6();

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
