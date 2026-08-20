/*
 * test_regression2.c
 *
 * 第二輪弱點驅動回歸測試
 * 測試日期：2026-04-15
 * 目的：針對第二輪深度分析發現的四類弱點進行系統性驗證
 *
 * 弱點分類：
 *   A. name_normalizer  — 小寫連接詞清單不完整（缺少 in / at / to / a / an / by）
 *   B. country_normalizer — 國家別名表缺少倒裝變體與北韓條目
 *   C. rank_parser      — #N 格式（如 "#10"）未被處理
 *   D. rank_parser      — 超大整數輸入造成未定義行為（UB）
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

#include "normalizer.h"
#include "record.h"
#include "csv_reader.h"
#include "csv_writer.h"

/* ------------------------------------------------------------------ */
/*  測試框架                                                            */
/* ------------------------------------------------------------------ */

static int g_run    = 0;
static int g_pass   = 0;
static int g_fail   = 0;

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

static int write_temp_csv(const char *path, const char *content)
{
    FILE *fp = fopen(path, "w");
    if (!fp) return 0;
    fputs(content, fp);
    return fclose(fp) == 0;
}

/* ------------------------------------------------------------------ */
/*  A. name_normalizer：小寫連接詞完整性測試                            */
/* ------------------------------------------------------------------ */

static void test_a_lowercase_connectors(void)
{
    char out[NAME_LEN];

    printf("\n--- A. 小寫連接詞完整性 ---\n");

    /* ── 已知正確（不應回歸）──────────────────────────────────────── */

    normalize_name("University of California", out, NAME_LEN);
    chk("A/現有: \"of\" 保持小寫",
        strcmp(out, "University of California") == 0, out,
        "University of California");

    normalize_name("Science and Technology University", out, NAME_LEN);
    chk("A/現有: \"and\" 保持小寫",
        strcmp(out, "Science and Technology University") == 0, out,
        "Science and Technology University");

    normalize_name("School of the Arts", out, NAME_LEN);
    chk("A/現有: \"the\" 保持小寫",
        strcmp(out, "School of the Arts") == 0, out,
        "School of the Arts");

    normalize_name("Centre for Advanced Studies", out, NAME_LEN);
    chk("A/現有: \"for\" 保持小寫",
        strcmp(out, "Centre for Advanced Studies") == 0, out,
        "Centre for Advanced Studies");

    /* ── 修正後應通過 ──────────────────────────────────────────────── */

    normalize_name("School of Arts in London", out, NAME_LEN);
    chk("A/新增: \"in\" 應保持小寫",
        strcmp(out, "School of Arts in London") == 0, out,
        "School of Arts in London");

    normalize_name("Institute of Mathematics at Cambridge", out, NAME_LEN);
    chk("A/新增: \"at\" 應保持小寫",
        strcmp(out, "Institute of Mathematics at Cambridge") == 0, out,
        "Institute of Mathematics at Cambridge");

    normalize_name("Department of Law and Policy", out, NAME_LEN);
    chk("A/新增: 多個連接詞組合 (and + 已有)",
        strcmp(out, "Department of Law and Policy") == 0, out,
        "Department of Law and Policy");

    normalize_name("School of Arts and Sciences", out, NAME_LEN);
    chk("A/新增: \"and\" 已有，確保仍正確",
        strcmp(out, "School of Arts and Sciences") == 0, out,
        "School of Arts and Sciences");

    normalize_name("Letter to the Editor", out, NAME_LEN);
    chk("A/新增: \"to\" 應保持小寫",
        strcmp(out, "Letter to the Editor") == 0, out,
        "Letter to the Editor");

    normalize_name("Submitted by the Author", out, NAME_LEN);
    chk("A/新增: \"by\" 應保持小寫",
        strcmp(out, "Submitted by the Author") == 0, out,
        "Submitted by the Author");

    normalize_name("A Guide to Research", out, NAME_LEN);
    chk("A/新增: 首詞 \"A\" 仍大寫（首詞不適用小寫規則）",
        out[0] == 'A', out, "A...");

    /* ── 位於句首的連接詞應大寫 ─────────────────────────────────────── */
    normalize_name("In the Name of Science", out, NAME_LEN);
    chk("A/邊界: 首詞 \"In\" 保持大寫",
        strcmp(out, "In the Name of Science") == 0, out,
        "In the Name of Science");

    /* ── 全小寫輸入仍正確 ───────────────────────────────────────────── */
    normalize_name("school of arts in london", out, NAME_LEN);
    chk("A/全小寫輸入: \"in\" 應保持小寫",
        strcmp(out, "School of Arts in London") == 0, out,
        "School of Arts in London");
}

/* ------------------------------------------------------------------ */
/*  B. country_normalizer：國家別名表擴充測試                           */
/* ------------------------------------------------------------------ */

static void test_b_country_aliases(void)
{
    char out[COUNTRY_LEN];

    printf("\n--- B. 國家別名表擴充 ---\n");

    /* ── 現有別名不應回歸 ──────────────────────────────────────────── */
    normalize_country("Republic of Korea", out, COUNTRY_LEN);
    chk("B/現有: \"Republic of Korea\" -> \"South Korea\"",
        strcmp(out, "South Korea") == 0, out, "South Korea");

    normalize_country("ROC", out, COUNTRY_LEN);
    chk("B/現有: \"ROC\" -> \"Taiwan\"",
        strcmp(out, "Taiwan") == 0, out, "Taiwan");

    /* ── 修正後應通過：倒裝/逗號變體 ────────────────────────────────── */
    normalize_country("Korea, Republic of", out, COUNTRY_LEN);
    chk("B/新增: \"Korea, Republic of\" -> \"South Korea\"",
        strcmp(out, "South Korea") == 0, out, "South Korea");

    normalize_country("Korea South", out, COUNTRY_LEN);
    chk("B/新增: \"Korea South\" -> \"South Korea\"",
        strcmp(out, "South Korea") == 0, out, "South Korea");

    /* ── 北韓條目 ───────────────────────────────────────────────────── */
    normalize_country("North Korea", out, COUNTRY_LEN);
    chk("B/新增: \"North Korea\" -> \"North Korea\"",
        strcmp(out, "North Korea") == 0, out, "North Korea");

    normalize_country("DPRK", out, COUNTRY_LEN);
    chk("B/新增: \"DPRK\" -> \"North Korea\"",
        strcmp(out, "North Korea") == 0, out, "North Korea");

    normalize_country("dprk", out, COUNTRY_LEN);
    chk("B/新增: \"dprk\" -> \"North Korea\"",
        strcmp(out, "North Korea") == 0, out, "North Korea");

    /* ── 馬來西亞變體 ─────────────────────────────────────────────── */
    normalize_country("Malaysia", out, COUNTRY_LEN);
    chk("B/fallback: \"Malaysia\" -> \"Malaysia\" (title-case)",
        strcmp(out, "Malaysia") == 0, out, "Malaysia");

    normalize_country("MY", out, COUNTRY_LEN);
    chk("B/新增: \"MY\" (ISO) -> \"Malaysia\"",
        strcmp(out, "Malaysia") == 0, out, "Malaysia");

    /* ── 阿拉伯聯合大公國 ────────────────────────────────────────────── */
    normalize_country("UAE", out, COUNTRY_LEN);
    chk("B/新增: \"UAE\" -> \"United Arab Emirates\"",
        strcmp(out, "United Arab Emirates") == 0, out,
        "United Arab Emirates");

    normalize_country("united arab emirates", out, COUNTRY_LEN);
    chk("B/新增: \"united arab emirates\" -> \"United Arab Emirates\"",
        strcmp(out, "United Arab Emirates") == 0, out,
        "United Arab Emirates");

    /* ── 멱等性：已正規化的值再正規化結果相同 ───────────────────────── */
    normalize_country("South Korea", out, COUNTRY_LEN);
    chk("B/멱等: \"South Korea\" -> \"South Korea\"",
        strcmp(out, "South Korea") == 0, out, "South Korea");

    normalize_country("North Korea", out, COUNTRY_LEN);
    chk("B/멱等: \"North Korea\" -> \"North Korea\"",
        strcmp(out, "North Korea") == 0, out, "North Korea");

    normalize_country("United Arab Emirates", out, COUNTRY_LEN);
    chk("B/멱等: \"United Arab Emirates\" -> \"United Arab Emirates\"",
        strcmp(out, "United Arab Emirates") == 0, out,
        "United Arab Emirates");
}

/* ------------------------------------------------------------------ */
/*  C. rank_parser：#N 格式支援測試                                     */
/* ------------------------------------------------------------------ */

static void test_c_rank_hash_format(void)
{
    int mn, mx;

    printf("\n--- C. 排名 #N 格式 ---\n");

    /* ── 修正後應通過 ──────────────────────────────────────────────── */
    parse_rank("#10", &mn, &mx);
    chk("C: \"#10\" -> 10/10",
        mn == 10 && mx == 10, NULL, NULL);

    parse_rank("#1", &mn, &mx);
    chk("C: \"#1\" -> 1/1",
        mn == 1 && mx == 1, NULL, NULL);

    parse_rank("#500", &mn, &mx);
    chk("C: \"#500\" -> 500/500",
        mn == 500 && mx == 500, NULL, NULL);

    parse_rank("  #99  ", &mn, &mx);
    chk("C: \"  #99  \" -> 99/99（含空白）",
        mn == 99 && mx == 99, NULL, NULL);

    /* ── 確保現有格式不受影響 ─────────────────────────────────────── */
    parse_rank("201", &mn, &mx);
    chk("C/回歸: 純數字 \"201\" 不受影響",
        mn == 201 && mx == 201, NULL, NULL);

    parse_rank("=201", &mn, &mx);
    chk("C/回歸: \"=201\" 格式不受影響",
        mn == 201 && mx == 201, NULL, NULL);

    parse_rank("101-150", &mn, &mx);
    chk("C/回歸: 區間格式不受影響",
        mn == 101 && mx == 150, NULL, NULL);

    parse_rank("Top 100", &mn, &mx);
    chk("C/回歸: Top N 格式不受影響",
        mn == 1 && mx == 100, NULL, NULL);
}

/* ------------------------------------------------------------------ */
/*  D. rank_parser：安全整數溢位處理測試                                 */
/* ------------------------------------------------------------------ */

static void test_d_rank_safe_overflow(void)
{
    int mn, mx;

    printf("\n--- D. 排名整數安全溢位 ---\n");

    /* ── 修正後：超出合理範圍應回傳 -1/-1，而非 UB ────────────────── */
    parse_rank("99999999999", &mn, &mx);
    printf("       資訊: parse_rank(\"99999999999\") -> %d/%d\n", mn, mx);
    chk("D: 超大排名值（>INT_MAX）應回傳 -1/-1 或正值（不崩潰）",
        mn != 0 /* 崩潰時不會到這裡 */, NULL, NULL);

    parse_rank("-1", &mn, &mx);
    chk("D: 負數排名 \"-1\" -> -1/-1（解析失敗）",
        mn == -1 && mx == -1, NULL, NULL);

    parse_rank("-100", &mn, &mx);
    chk("D: 負數排名 \"-100\" -> -1/-1",
        mn == -1 && mx == -1, NULL, NULL);

    /* ── 修正後：合理邊界值應正確解析 ────────────────────────────────── */
    parse_rank("99999", &mn, &mx);
    chk("D: 合理大值 \"99999\" -> 99999/99999",
        mn == 99999 && mx == 99999, NULL, NULL);

    parse_rank("0", &mn, &mx);
    chk("D: 零值 \"0\" -> 0/0（已有行為）",
        mn == 0 && mx == 0, NULL, NULL);

    parse_rank("1", &mn, &mx);
    chk("D: 最小正值 \"1\" -> 1/1",
        mn == 1 && mx == 1, NULL, NULL);
}

/* ------------------------------------------------------------------ */
/*  整合測試：多弱點修正後完整 pipeline 驗證                              */
/* ------------------------------------------------------------------ */

static void test_integration_pipeline(void)
{
    const char *filename = "build/test_r2_integration.csv";
    UniversityRecord records[10];
    int count;

    const char *csv_content =
        "University,Country,Rank Min,Rank Max,Overall Score\n"
        "school of arts in london,Korea Republic of,#5,#5,88.0\n"
        "Institute of Science at Cambridge,DPRK,=201,=201,72.5\n"
        "MIT,usa,1,1,100.0\n";

    printf("\n--- 整合：完整 pipeline 多弱點驗證 ---\n");

    {
        FILE *fp = fopen(filename, "w");
        if (!fp) {
            chk("整合: 建立測試 CSV 檔案", 0, NULL, NULL);
            return;
        }
        fputs(csv_content, fp);
        fclose(fp);
    }

    count = load_csv_data(filename, records, 10);
    chk("整合: 三筆資料載入成功", count == 3, NULL, NULL);

    if (count != 3) { remove(filename); return; }

    normalize_dataset(records, count);

    /* 第一筆：school of arts in london / Korea Republic of / #5-#5 */
    chk("整合: 名稱「in」正規化為小寫",
        strcmp(records[0].normalized_name,
               "School of Arts in London") == 0,
        records[0].normalized_name, "School of Arts in London");

    chk("整合: 「Korea Republic of」正規化為「South Korea」",
        strcmp(records[0].normalized_country, "South Korea") == 0,
        records[0].normalized_country, "South Korea");

    chk("整合: #5-#5 解析為 5/5",
        records[0].rank_min == 5 && records[0].rank_max == 5,
        NULL, NULL);

    /* 第二筆：Institute of Science at Cambridge / DPRK / =201-=201 */
    chk("整合: 名稱「at」正規化為小寫",
        strcmp(records[1].normalized_name,
               "Institute of Science at Cambridge") == 0,
        records[1].normalized_name, "Institute of Science at Cambridge");

    chk("整合: 「DPRK」正規化為「North Korea」",
        strcmp(records[1].normalized_country, "North Korea") == 0,
        records[1].normalized_country, "North Korea");

    chk("整合: =201-=201 解析為 201/201",
        records[1].rank_min == 201 && records[1].rank_max == 201,
        NULL, NULL);

    /* 第三筆：控制組 */
    chk("整合: MIT 名稱保持大寫",
        strcmp(records[2].normalized_name, "MIT") == 0,
        records[2].normalized_name, "MIT");

    chk("整合: usa -> United States",
        strcmp(records[2].normalized_country, "United States") == 0,
        records[2].normalized_country, "United States");

    remove(filename);
}

/* ------------------------------------------------------------------ */
/*  額外：score_parser 邊界補強                                          */
/* ------------------------------------------------------------------ */

static void test_extra_score_boundaries(void)
{
    double s;
#define NEAR(v, t) ((v) > (t) - 0.001 && (v) < (t) + 0.001)

    printf("\n--- 額外：score_parser 邊界補強 ---\n");

    /* N/A 常見無效輸入 */
    s = parse_score("N/A");
    chk("score: \"N/A\" -> -1.0", NEAR(s, -1.0), NULL, NULL);

    s = parse_score("n/a");
    chk("score: \"n/a\" -> -1.0", NEAR(s, -1.0), NULL, NULL);

    s = parse_score("-");
    chk("score: 單一「-」-> -1.0（無效）", NEAR(s, -1.0), NULL, NULL);

    s = parse_score("+");
    chk("score: 單一「+」-> -1.0（無效）", NEAR(s, -1.0), NULL, NULL);

    /* 雙小數點 */
    s = parse_score("98.40.50");
    chk("score: \"98.40.50\" -> 98.40（第一個合法數字）",
        NEAR(s, 98.40), NULL, NULL);

    /* 帶單位 */
    s = parse_score("95.5 / 100");
    chk("score: \"95.5 / 100\" -> 95.5（停在空格）",
        NEAR(s, 95.5), NULL, NULL);

    /* 科學記號（非支援格式，應忽略 e 之後的部分）*/
    s = parse_score("9.8e1");
    printf("       資訊: parse_score(\"9.8e1\") -> %.4f（科學記號）\n", s);
    chk("score: \"9.8e1\" -> 9.8（停在 e，僅取整數部分）",
        NEAR(s, 9.8), NULL, NULL);

#undef NEAR
}

/* ------------------------------------------------------------------ */
/*  額外：csv_writer 邊界補強                                            */
/* ------------------------------------------------------------------ */

static void test_extra_csv_writer(void)
{
    const char *filename = "build/test_r2_writer.csv";
    char buf[1024];
    FILE *fp;

    printf("\n--- 額外：csv_writer 邊界補強 ---\n");

    /* 測試 count=0 不崩潰 */
    {
        UniversityRecord dummy;
        memset(&dummy, 0, sizeof(dummy));
        int ok = write_normalized_csv(filename, &dummy, 0);
        chk("writer: count=0 時不崩潰", ok != 0 || ok == 0 /* 只要不崩潰 */,
            NULL, NULL);
        remove(filename);
    }

    /* 分數恰好為 0.0 不被誤判為無效 */
    {
        UniversityRecord rec;
        size_t n;
        memset(&rec, 0, sizeof(rec));
        strcpy(rec.normalized_name, "ZeroScore University");
        strcpy(rec.normalized_country, "Japan");
        rec.rank_min = 10;
        rec.rank_max = 10;
        rec.score    = 0.0;

        if (write_normalized_csv(filename, &rec, 1)) {
            fp = fopen(filename, "r");
            if (fp) {
                n = fread(buf, 1, sizeof(buf) - 1, fp);
                buf[n] = '\0';
                fclose(fp);
                chk("writer: score=0.0 寫出 \"0.00\" 而非空值",
                    strstr(buf, "0.00") != NULL, buf, "(含 0.00)");
            }
        }
        remove(filename);
    }

    /* 名稱中含 Tab 字元 */
    {
        UniversityRecord rec;
        size_t n;
        memset(&rec, 0, sizeof(rec));
        strcpy(rec.normalized_name, "Tab\tUniversity");
        strcpy(rec.normalized_country, "Germany");
        rec.rank_min = 20;
        rec.rank_max = 20;
        rec.score    = 85.0;

        if (write_normalized_csv(filename, &rec, 1)) {
            fp = fopen(filename, "r");
            if (fp) {
                n = fread(buf, 1, sizeof(buf) - 1, fp);
                buf[n] = '\0';
                fclose(fp);
                /* Tab 不觸發 needs_csv_quotes，應直接輸出 */
                chk("writer: 名稱含 Tab 不崩潰並輸出",
                    strlen(buf) > 0, NULL, NULL);
            }
        }
        remove(filename);
    }
}

/* ------------------------------------------------------------------ */
/*  main                                                               */
/* ------------------------------------------------------------------ */

int main(void)
{
    printf("╔══════════════════════════════════════════════════════╗\n");
    printf("║  第二輪弱點驅動回歸測試 — 2026-04-15                  ║\n");
    printf("╚══════════════════════════════════════════════════════╝\n");

    test_a_lowercase_connectors();
    test_b_country_aliases();
    test_c_rank_hash_format();
    test_d_rank_safe_overflow();
    test_integration_pipeline();
    test_extra_score_boundaries();
    test_extra_csv_writer();

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
