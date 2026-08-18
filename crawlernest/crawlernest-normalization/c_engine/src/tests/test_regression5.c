/*
 * test_regression5.c
 *
 * 第五輪弱點驅動回歸測試
 * 測試日期：2026-04-21
 * 目的：針對 Session 5 深度探測發現的三類弱點進行系統性驗證
 *
 * 弱點分類：
 *   M. csv_reader     — rank_min/rank_max 欄位其中一個為空時
 *                       snprintf "%s-%s" 產生 "-150" 之類的負數字串，
 *                       被 rank_parser 拒絕 → 排名資訊遺失
 *   P. rank_parser    — "TOP 0" 解析為 rank_min=1, rank_max=0（min > max），
 *                       語意矛盾；應拒絕並回傳 -1/-1
 *   Q. rank_parser    — 反轉區間 "150-101" 解析後 rank_min=150 > rank_max=101，
 *                       違反 min <= max 語義；現改為自動交換
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
/*  M. csv_reader：rank 欄位部分空白處理                                */
/* ------------------------------------------------------------------ */

static void test_m_rank_field_combination(void)
{
    const char *in_file = "build/test_r5_m_in.csv";
    UniversityRecord records[10];
    int count;
    FILE *fp;

    /*
     * 測試矩陣：
     *   Row 0: rank_min 空,  rank_max=150  → 應解析為 150/150
     *   Row 1: rank_min=101, rank_max 空   → 應解析為 101/101
     *   Row 2: rank_min 空,  rank_max 空   → 應解析為 -1/-1（無排名）
     *   Row 3: rank_min=101, rank_max=150  → 應解析為 101/150
     *   Row 4: rank_min=1,   rank_max=10   → 應解析為 1/10（正常範圍）
     */
    const char *csv_content =
        "University,Country,Rank Min,Rank Max,Overall Score\n"
        "Alpha University,Japan,,150,80.0\n"
        "Beta University,Japan,101,,75.0\n"
        "Gamma University,Japan,,,70.0\n"
        "Delta University,Japan,101,150,65.0\n"
        "Epsilon University,Japan,1,10,90.0\n";

    printf("\n--- M. csv_reader rank 欄位部分空白處理 ---\n");

    fp = fopen(in_file, "w");
    if (!fp) {
        chk("M: 建立測試 CSV 失敗", 0, NULL, NULL);
        return;
    }
    fputs(csv_content, fp);
    fclose(fp);

    count = load_csv_data(in_file, records, 10);
    chk("M: 五筆資料載入成功",
        count == 5, NULL, NULL);

    if (count != 5) {
        remove(in_file);
        return;
    }

    normalize_dataset(records, count);

    /* Row 0: rank_min 空, rank_max=150 → parse "150" → 150/150 */
    chk("M: rank_min 空, rank_max=150 → rank_min=150",
        records[0].rank_min == 150, NULL, NULL);
    chk("M: rank_min 空, rank_max=150 → rank_max=150",
        records[0].rank_max == 150, NULL, NULL);

    /* Row 1: rank_min=101, rank_max 空 → parse "101" → 101/101 */
    chk("M: rank_min=101, rank_max 空 → rank_min=101",
        records[1].rank_min == 101, NULL, NULL);
    chk("M: rank_min=101, rank_max 空 → rank_max=101",
        records[1].rank_max == 101, NULL, NULL);

    /* Row 2: 兩者皆空 → -1/-1 */
    chk("M: rank_min 空, rank_max 空 → rank_min=-1",
        records[2].rank_min == -1, NULL, NULL);
    chk("M: rank_min 空, rank_max 空 → rank_max=-1",
        records[2].rank_max == -1, NULL, NULL);

    /* Row 3: 兩者皆有值 → 101/150（行為不變） */
    chk("M/回歸: rank_min=101, rank_max=150 → rank_min=101",
        records[3].rank_min == 101, NULL, NULL);
    chk("M/回歸: rank_min=101, rank_max=150 → rank_max=150",
        records[3].rank_max == 150, NULL, NULL);

    /* Row 4: 正常範圍 1-10 → 1/10 */
    chk("M/回歸: rank_min=1, rank_max=10 → rank_min=1",
        records[4].rank_min == 1, NULL, NULL);
    chk("M/回歸: rank_min=1, rank_max=10 → rank_max=10",
        records[4].rank_max == 10, NULL, NULL);

    /* rank_min 應永遠 <= rank_max */
    {
        int i;
        int all_valid = 1;
        for (i = 0; i < count; i++) {
            if (records[i].rank_min >= 0 &&
                records[i].rank_min > records[i].rank_max) {
                all_valid = 0;
                break;
            }
        }
        chk("M: 所有有效排名均滿足 rank_min <= rank_max",
            all_valid, NULL, NULL);
    }

    remove(in_file);
}

/* ------------------------------------------------------------------ */
/*  P. rank_parser：TOP 0 拒絕                                         */
/* ------------------------------------------------------------------ */

static void test_p_top_zero(void)
{
    int mn, mx;

    printf("\n--- P. rank_parser: TOP 0 拒絕 ---\n");

    /* 主要修正案例 */
    parse_rank("TOP 0", &mn, &mx);
    chk("P: \"TOP 0\" -> -1/-1（拒絕語意矛盾）",
        mn == -1 && mx == -1, NULL, NULL);

    parse_rank("top 0", &mn, &mx);
    chk("P: \"top 0\" (小寫) -> -1/-1",
        mn == -1 && mx == -1, NULL, NULL);

    parse_rank("Top 0", &mn, &mx);
    chk("P: \"Top 0\" (混合) -> -1/-1",
        mn == -1 && mx == -1, NULL, NULL);

    /* 邊界：TOP 1 仍然有效 */
    parse_rank("TOP 1", &mn, &mx);
    chk("P/邊界: \"TOP 1\" -> 1/1（有效）",
        mn == 1 && mx == 1, NULL, NULL);

    /* 回歸：正常 TOP N 仍正確 */
    parse_rank("TOP 10", &mn, &mx);
    chk("P/回歸: \"TOP 10\" -> 1/10",
        mn == 1 && mx == 10, NULL, NULL);

    parse_rank("TOP 100", &mn, &mx);
    chk("P/回歸: \"TOP 100\" -> 1/100",
        mn == 1 && mx == 100, NULL, NULL);

    parse_rank("TOP 50", &mn, &mx);
    chk("P/回歸: \"TOP 50\" -> 1/50",
        mn == 1 && mx == 50, NULL, NULL);

    /* TOP 後跟負數 — 應被拒絕（safe_parse_int 拒絕負值） */
    parse_rank("TOP -5", &mn, &mx);
    chk("P/邊界: \"TOP -5\" -> -1/-1（負數被拒）",
        mn == -1 && mx == -1, NULL, NULL);

    /* TOP 後跟非數字 */
    parse_rank("TOP abc", &mn, &mx);
    chk("P/邊界: \"TOP abc\" -> -1/-1（非數字）",
        mn == -1 && mx == -1, NULL, NULL);
}

/* ------------------------------------------------------------------ */
/*  Q. rank_parser：反轉區間自動修正                                    */
/* ------------------------------------------------------------------ */

static void test_q_range_reversal(void)
{
    int mn, mx;

    printf("\n--- Q. rank_parser: 反轉區間自動修正 ---\n");

    /* 主要修正案例 */
    parse_rank("150-101", &mn, &mx);
    chk("Q: \"150-101\" -> rank_min=101",
        mn == 101, NULL, NULL);
    chk("Q: \"150-101\" -> rank_max=150",
        mx == 150, NULL, NULL);

    parse_rank("500-201", &mn, &mx);
    chk("Q: \"500-201\" -> rank_min=201",
        mn == 201, NULL, NULL);
    chk("Q: \"500-201\" -> rank_max=500",
        mx == 500, NULL, NULL);

    parse_rank("1000-1", &mn, &mx);
    chk("Q: \"1000-1\" -> rank_min=1",
        mn == 1, NULL, NULL);
    chk("Q: \"1000-1\" -> rank_max=1000",
        mx == 1000, NULL, NULL);

    /* 相等值：min == max（等值區間，仍然有效） */
    parse_rank("50-50", &mn, &mx);
    chk("Q/邊界: \"50-50\" -> 50/50（等值區間有效）",
        mn == 50 && mx == 50, NULL, NULL);

    /* 回歸：正向區間不受影響 */
    parse_rank("101-150", &mn, &mx);
    chk("Q/回歸: \"101-150\" -> 101/150（正向區間正確）",
        mn == 101 && mx == 150, NULL, NULL);

    parse_rank("1-100", &mn, &mx);
    chk("Q/回歸: \"1-100\" -> 1/100",
        mn == 1 && mx == 100, NULL, NULL);

    parse_rank("201-250", &mn, &mx);
    chk("Q/回歸: \"201-250\" -> 201/250",
        mn == 201 && mx == 250, NULL, NULL);

    /* en dash 反轉（先正規化為 '-'，然後 Q 修正） */
    /* "150–101" (en dash, UTF-8 E2 80 93) */
    parse_rank("150\xe2\x80\x93""101", &mn, &mx);
    chk("Q: \"150–101\" (en dash 反轉) -> 101/150",
        mn == 101 && mx == 150, NULL, NULL);

    /* 確保所有結果 rank_min <= rank_max */
    {
        struct { const char *s; int exp_mn; int exp_mx; } cases[] = {
            {"300-100", 100, 300},
            {"99-1",    1,   99},
            {"10-5",    5,   10},
        };
        int i;
        for (i = 0; i < 3; i++) {
            parse_rank(cases[i].s, &mn, &mx);
            chk("Q/批次: 反轉後 rank_min <= rank_max",
                mn == cases[i].exp_mn && mx == cases[i].exp_mx,
                NULL, NULL);
        }
    }
}

/* ------------------------------------------------------------------ */
/*  整合測試：Session 5 三類修正完整 pipeline 驗證                     */
/* ------------------------------------------------------------------ */

static void test_integration_s5(void)
{
    const char *in_file  = "build/test_r5_int_in.csv";
    const char *out_file = "build/test_r5_int_out.csv";
    UniversityRecord records[10];
    int count;
    FILE *fp;
    char buf[4096];
    size_t n;

    /*
     * CSV 設計：
     * - Row 0: rank_min 空, rank_max=50 → Fix M → 50/50
     * - Row 1: rank 反轉 "150-101"      → Fix Q → 101/150
     * - Row 2: TOP 0 （語意矛盾）       → Fix P → -1/-1（無效，空輸出）
     * - Row 3: 正常 "TOP 10"            → 1/10（回歸）
     * - Row 4: 正常 "101-150"           → 101/150（回歸）
     */
    const char *csv_content =
        "University,Country,Rank Min,Rank Max,Overall Score\n"
        "Alpha University,Japan,,50,80.0\n"
        "Beta University,USA,150,101,75.0\n"
        "Gamma University,UK,TOP 0,TOP 0,70.0\n"
        "Delta University,France,TOP 10,TOP 10,90.0\n"
        "Epsilon University,Germany,101,150,85.0\n";

    printf("\n--- 整合：Session 5 三類修正完整 pipeline 驗證 ---\n");

    fp = fopen(in_file, "w");
    if (!fp) { chk("整合: 建立 CSV 失敗", 0, NULL, NULL); return; }
    fputs(csv_content, fp);
    fclose(fp);

    count = load_csv_data(in_file, records, 10);
    chk("整合: 五筆資料載入成功", count == 5, NULL, NULL);
    if (count != 5) { remove(in_file); return; }

    normalize_dataset(records, count);

    /* Fix M: rank_min 空, rank_max=50 → 50/50 */
    chk("整合/M: rank_min 空 → rank_min=50",
        records[0].rank_min == 50, NULL, NULL);
    chk("整合/M: rank_min 空 → rank_max=50",
        records[0].rank_max == 50, NULL, NULL);

    /* Fix Q: "150-101" → 101/150 */
    chk("整合/Q: 反轉 \"150-101\" → rank_min=101",
        records[1].rank_min == 101, NULL, NULL);
    chk("整合/Q: 反轉 \"150-101\" → rank_max=150",
        records[1].rank_max == 150, NULL, NULL);

    /* Fix P: "TOP 0" → -1/-1 */
    chk("整合/P: \"TOP 0\" → rank_min=-1",
        records[2].rank_min == -1, NULL, NULL);
    chk("整合/P: \"TOP 0\" → rank_max=-1",
        records[2].rank_max == -1, NULL, NULL);

    /* 回歸: TOP 10 → 1/10 */
    chk("整合/回歸: \"TOP 10\" → rank_min=1",
        records[3].rank_min == 1, NULL, NULL);
    chk("整合/回歸: \"TOP 10\" → rank_max=10",
        records[3].rank_max == 10, NULL, NULL);

    /* 回歸: 101-150 → 101/150 */
    chk("整合/回歸: \"101-150\" → rank_min=101",
        records[4].rank_min == 101, NULL, NULL);
    chk("整合/回歸: \"101-150\" → rank_max=150",
        records[4].rank_max == 150, NULL, NULL);

    /* 全局不變式：有效排名均滿足 rank_min <= rank_max */
    {
        int i, ok = 1;
        for (i = 0; i < count; i++) {
            if (records[i].rank_min >= 0 &&
                records[i].rank_min > records[i].rank_max) {
                ok = 0;
                break;
            }
        }
        chk("整合/不變式: 所有有效排名 rank_min <= rank_max", ok, NULL, NULL);
    }

    /* CSV 寫出不含 -1,-1 */
    chk("整合/寫出: write_normalized_csv 成功",
        write_normalized_csv(out_file, records, count) == 1, NULL, NULL);

    fp = fopen(out_file, "r");
    if (fp) {
        n = fread(buf, 1, sizeof(buf) - 1, fp);
        buf[n] = '\0';
        fclose(fp);
        chk("整合/寫出: 輸出不含 \"-1,-1\"",
            strstr(buf, "-1,-1") == NULL, buf, "(不含 -1,-1)");
    }

    remove(in_file);
    remove(out_file);
}

/* ------------------------------------------------------------------ */
/*  額外：邊界與回歸補強                                                */
/* ------------------------------------------------------------------ */

static void test_extra_s5(void)
{
    int mn, mx;

    printf("\n--- 額外：邊界與回歸補強 ---\n");

    /* rank_parser 核心格式回歸（確保本次修正未破壞既有行為） */
    parse_rank("53", &mn, &mx);
    chk("回歸: 純數字 \"53\" -> 53/53",
        mn == 53 && mx == 53, NULL, NULL);

    parse_rank("Rank 53", &mn, &mx);
    chk("回歸: \"Rank 53\" -> 53/53",
        mn == 53 && mx == 53, NULL, NULL);

    parse_rank("=201", &mn, &mx);
    chk("回歸: \"=201\" -> 201/201",
        mn == 201 && mx == 201, NULL, NULL);

    parse_rank("201+", &mn, &mx);
    chk("回歸: \"201+\" -> 201/201",
        mn == 201 && mx == 201, NULL, NULL);

    parse_rank("#10", &mn, &mx);
    chk("回歸: \"#10\" -> 10/10",
        mn == 10 && mx == 10, NULL, NULL);

    parse_rank("101-150", &mn, &mx);
    chk("回歸: 區間 \"101-150\" -> 101/150",
        mn == 101 && mx == 150, NULL, NULL);

    /* en dash 正向（之前通過，需確認仍通過） */
    parse_rank("201\xe2\x80\x93""250", &mn, &mx);
    chk("回歸: \"201–250\" (en dash) -> 201/250",
        mn == 201 && mx == 250, NULL, NULL);

    /* NULL/空字串仍安全 */
    parse_rank(NULL, &mn, &mx);
    chk("回歸: NULL -> -1/-1", mn == -1 && mx == -1, NULL, NULL);

    parse_rank("", &mn, &mx);
    chk("回歸: 空字串 -> -1/-1", mn == -1 && mx == -1, NULL, NULL);

    /* 溢位保護（Fix L 仍有效） */
    parse_rank("9999999999", &mn, &mx);
    chk("回歸/L: 溢位數字 -> -1/-1",
        mn == -1 && mx == -1, NULL, NULL);

    parse_rank("9999999", &mn, &mx);
    chk("回歸/L: MAX_REASONABLE=9999999 -> 9999999/9999999",
        mn == 9999999 && mx == 9999999, NULL, NULL);

    /* TOP N 大小寫不敏感（Fix I 仍有效） */
    parse_rank("TOP 200", &mn, &mx);
    chk("回歸/I: \"TOP 200\" -> 1/200",
        mn == 1 && mx == 200, NULL, NULL);

    parse_rank("RANK 99", &mn, &mx);
    chk("回歸/I: \"RANK 99\" -> 99/99",
        mn == 99 && mx == 99, NULL, NULL);
}

/* ------------------------------------------------------------------ */
/*  main                                                               */
/* ------------------------------------------------------------------ */

int main(void)
{
    printf("╔══════════════════════════════════════════════════════╗\n");
    printf("║  第五輪弱點驅動回歸測試 — 2026-04-21                  ║\n");
    printf("╚══════════════════════════════════════════════════════╝\n");

    test_m_rank_field_combination();
    test_p_top_zero();
    test_q_range_reversal();
    test_integration_s5();
    test_extra_s5();

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
