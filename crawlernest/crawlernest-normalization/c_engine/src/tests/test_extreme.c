/*
 * test_extreme.c
 *
 * Extreme stress and edge-case tests for the Clawer C Data Normalization Engine.
 *
 * Test categories:
 *   1.  NULL / empty safety
 *   2.  Single character
 *   3.  Buffer boundary (near / over field limits)
 *   4.  Unicode / multi-byte passthrough
 *   5.  Adversarial / injection inputs
 *   6.  Country alias exhaustion
 *   7.  Abbreviation expansion edge cases
 *   8.  Idempotency (normalize twice == normalize once)
 *   9.  Rank parsing edge cases
 *  10.  Score parsing edge cases
 *  11.  Name normalization edge cases
 *  12.  Throughput (10 000 records, < 5 s)
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "normalizer.h"
#include "record.h"
#include "csv_reader.h"
#include "csv_writer.h"

/* ------------------------------------------------------------------ */
/*  Minimal test harness                                               */
/* ------------------------------------------------------------------ */

static int g_tests_run    = 0;
static int g_tests_passed = 0;
static int g_tests_failed = 0;

static void check(const char *label, int passed,
                  const char *actual, const char *expected)
{
    g_tests_run++;
    if (passed) {
        g_tests_passed++;
        printf("[PASS] %s\n", label);
    } else {
        g_tests_failed++;
        printf("[FAIL] %s\n", label);
        if (actual && expected)
            printf("       expected: \"%s\"\n       actual:   \"%s\"\n",
                   expected, actual);
    }
}

/* ------------------------------------------------------------------ */
/*  1.  NULL / empty safety                                            */
/* ------------------------------------------------------------------ */

static void test_null_safety(void)
{
    char out[NAME_LEN];
    int  mn, mx;

    normalize_name(NULL, NULL,  NAME_LEN);
    normalize_name("X",  NULL,  NAME_LEN);
    normalize_name(NULL, out,   NAME_LEN);
    normalize_name("X",  out,   0);
    normalize_name("X",  out,  -1);

    normalize_country(NULL, NULL,    COUNTRY_LEN);
    normalize_country("X",  NULL,    COUNTRY_LEN);
    normalize_country(NULL, out,     COUNTRY_LEN);
    normalize_country("X",  out,     0);

    parse_rank(NULL, NULL, NULL);
    parse_rank("10", NULL, NULL);
    parse_rank(NULL, &mn,  &mx);

    parse_score(NULL);

    check("null_safety: all NULL inputs do not crash", 1, NULL, NULL);
}

static void test_empty_string(void)
{
    char   out[NAME_LEN];
    int    mn = 999, mx = 999;
    double sc;

    normalize_name("", out, NAME_LEN);
    check("empty: normalize_name(\"\") -> \"\"",
          strcmp(out, "") == 0, out, "");

    normalize_country("", out, COUNTRY_LEN);
    check("empty: normalize_country(\"\") -> \"\"",
          strcmp(out, "") == 0, out, "");

    parse_rank("", &mn, &mx);
    check("empty: parse_rank(\"\") -> -1/-1",
          mn == -1 && mx == -1, NULL, NULL);

    sc = parse_score("");
    check("empty: parse_score(\"\") -> -1.0",
          sc < -0.9 && sc > -1.1, NULL, NULL);
}

static void test_whitespace_only(void)
{
    char out[NAME_LEN];

    normalize_name("   \t\n  ", out, NAME_LEN);
    check("whitespace: normalize_name -> \"\"",
          strcmp(out, "") == 0, out, "");

    normalize_country("   ", out, COUNTRY_LEN);
    check("whitespace: normalize_country -> \"\"",
          strcmp(out, "") == 0, out, "");
}

/* ------------------------------------------------------------------ */
/*  2.  Single character                                               */
/* ------------------------------------------------------------------ */

static void test_single_char(void)
{
    char out[NAME_LEN];

    normalize_name("A", out, NAME_LEN);
    check("single_char: \"A\" -> \"A\"",
          strcmp(out, "A") == 0, out, "A");

    normalize_name("x", out, NAME_LEN);
    check("single_char: \"x\" -> \"X\"",
          strcmp(out, "X") == 0, out, "X");

    normalize_country("a", out, COUNTRY_LEN);
    check("single_char: country \"a\" -> title case \"A\"",
          strcmp(out, "A") == 0, out, "A");
}

/* ------------------------------------------------------------------ */
/*  3.  Buffer boundary                                                */
/* ------------------------------------------------------------------ */

static void test_buffer_boundary(void)
{
    /* NAME_WORK_LEN is 512 (internal to name_normalizer.c) */
    enum { WORK_LEN = 512 };
    char input[WORK_LEN + 4];
    char out[NAME_LEN];
    int  i;

    /* 149 consecutive 'a' chars — max valid NAME_LEN content */
    for (i = 0; i < NAME_LEN - 1; i++) input[i] = 'a';
    input[NAME_LEN - 1] = '\0';
    normalize_name(input, out, NAME_LEN);
    check("boundary: 149-char name does not crash", 1, NULL, NULL);
    check("boundary: 149-char output within NAME_LEN",
          (int)strlen(out) < NAME_LEN, NULL, NULL);

    /* 511 chars — fills the 512-byte working buffer exactly */
    for (i = 0; i < WORK_LEN - 1; i++) input[i] = 'b';
    input[WORK_LEN - 1] = '\0';
    normalize_name(input, out, NAME_LEN);
    check("boundary: 511-char name truncated safely",
          (int)strlen(out) < NAME_LEN, NULL, NULL);

    /* Single 100-char word with no spaces — tests internal word buffer */
    for (i = 0; i < 100; i++) input[i] = 'c';
    input[100] = '\0';
    normalize_name(input, out, NAME_LEN);
    check("boundary: 100-char single token -> no phantom space split",
          strchr(out, ' ') == NULL, out, "(no spaces)");
}

/* ------------------------------------------------------------------ */
/*  4.  Unicode / multi-byte passthrough                               */
/* ------------------------------------------------------------------ */

static void test_unicode(void)
{
    char out[NAME_LEN];

    /* CJK — 12 UTF-8 bytes, should pass through unchanged */
    normalize_name("\xe5\x8c\x97\xe4\xba\xac\xe5\xa4\xa7\xe5\xad\xa6",
                   out, NAME_LEN);
    check("unicode: Chinese \"北京大学\" passes through unchanged",
          strcmp(out, "\xe5\x8c\x97\xe4\xba\xac\xe5\xa4\xa7\xe5\xad\xa6") == 0,
          out, "北京大学");

    /* Arabic — two words with ASCII space between */
    normalize_name("\xd8\xac\xd8\xa7\xd9\x85\xd8\xb9\xd8\xa9 \xd8\xa7\xd9\x84\xd9\x82\xd8\xa7\xd9\x87\xd8\xb1\xd8\xa9",
                   out, NAME_LEN);
    check("unicode: Arabic RTL text does not crash", 1, NULL, NULL);
    check("unicode: Arabic output non-empty", strlen(out) > 0, NULL, NULL);

    /* 4-byte emoji (U+1F393 🎓) embedded in ASCII name */
    normalize_name("University \xf0\x9f\x8e\x93 of Tech", out, NAME_LEN);
    check("unicode: emoji in ASCII name does not crash", 1, NULL, NULL);

    /* Precomposed É (U+00C9, UTF-8: 0xC3 0x89) — capital E with acute.
     * Split the string literal so the compiler does not interpret
     * 0x89 followed by 'c' as a single multi-digit escape. */
    normalize_name("\xc3\x89" "cole Polytechnique", out, NAME_LEN);
    check("unicode: precomposed \xc3\x89 passes through as capital",
          strcmp(out, "\xc3\x89" "cole Polytechnique") == 0,
          out, "\xc3\x89" "cole Polytechnique");

    /* Country with non-ASCII chars falls back to title case without crash */
    normalize_country("\xc3\xb6sterreich", out, COUNTRY_LEN); /* österreich */
    check("unicode: non-ASCII country does not crash", 1, NULL, NULL);
}

/* ------------------------------------------------------------------ */
/*  5.  Adversarial / injection inputs                                 */
/* ------------------------------------------------------------------ */

static void test_adversarial(void)
{
    char out[NAME_LEN];

    /* SQL-like injection */
    normalize_name("'; DROP TABLE universities; --", out, NAME_LEN);
    check("adversarial: SQL injection does not crash", 1, NULL, NULL);
    check("adversarial: SQL injection produces output",
          strlen(out) > 0, NULL, NULL);

    /* Shell metacharacters */
    normalize_name("$(rm -rf /)", out, NAME_LEN);
    check("adversarial: shell metachar does not crash", 1, NULL, NULL);

    /* Internal newline and tab — should collapse to spaces */
    normalize_name("Univ\nof\tTech", out, NAME_LEN);
    check("adversarial: \\n and \\t collapsed and normalised (Fix G: Tech 不展開)",
          strcmp(out, "University of Tech") == 0,
          out, "University of Tech");

    /* CRLF suffix — must be trimmed */
    normalize_name("MIT\r\n", out, NAME_LEN);
    check("adversarial: CRLF trimmed -> \"MIT\"",
          strcmp(out, "MIT") == 0, out, "MIT");

    /* Empty input always produces empty output */
    out[0] = 'X';
    normalize_name("", out, NAME_LEN);
    check("adversarial: empty input always produces empty output",
          out[0] == '\0', NULL, NULL);

    /* Percent-encoded lookalike */
    normalize_name("%20MIT%20", out, NAME_LEN);
    check("adversarial: percent-encoded string does not crash", 1, NULL, NULL);
}

/* ------------------------------------------------------------------ */
/*  6.  Country alias exhaustion                                       */
/* ------------------------------------------------------------------ */

static void test_country_aliases(void)
{
    char out[COUNTRY_LEN];

    typedef struct { const char *in; const char *want; } Case;
    static const Case cases[] = {
        /* USA */
        {"usa",                       "United States"},
        {"USA",                       "United States"},
        {"U.S.A.",                    "United States"},
        {"us",                        "United States"},
        {"US",                        "United States"},
        {"united states",             "United States"},
        {"United States",             "United States"},
        {"united states of america",  "United States"},
        /* UK and constituent countries */
        {"uk",                        "United Kingdom"},
        {"UK",                        "United Kingdom"},
        {"u.k.",                      "United Kingdom"},
        {"united kingdom",            "United Kingdom"},
        {"great britain",             "United Kingdom"},
        {"britain",                   "United Kingdom"},
        {"england",                   "United Kingdom"},
        {"scotland",                  "United Kingdom"},
        {"wales",                     "United Kingdom"},
        {"northern ireland",          "United Kingdom"},
        /* Singapore */
        {"sg",                        "Singapore"},
        {"SG",                        "Singapore"},
        {"singapore",                 "Singapore"},
        /* China */
        {"china",                     "China (Mainland)"},
        {"China",                     "China (Mainland)"},
        {"mainland china",            "China (Mainland)"},
        {"china mainland",            "China (Mainland)"},
        {"prc",                       "China (Mainland)"},
        {"peoples republic of china", "China (Mainland)"},
        /* Hong Kong */
        {"hong kong",                 "Hong Kong SAR"},
        {"hong kong sar",             "Hong Kong SAR"},
        /* Taiwan */
        {"taiwan",                    "Taiwan"},
        {"roc",                       "Taiwan"},
        {"ROC",                       "Taiwan"},
        {"republic of china",         "Taiwan"},
        /* South Korea */
        {"south korea",               "South Korea"},
        {"korea",                     "South Korea"},
        {"Korea",                     "South Korea"},
        {"republic of korea",         "South Korea"},
        {NULL, NULL}
    };

    for (int i = 0; cases[i].in != NULL; i++) {
        char label[160];
        snprintf(label, sizeof(label),
                 "country_alias: \"%s\" -> \"%s\"",
                 cases[i].in, cases[i].want);
        normalize_country(cases[i].in, out, COUNTRY_LEN);
        check(label, strcmp(out, cases[i].want) == 0, out, cases[i].want);
    }

    /* Title-case fallback for unmapped countries */
    normalize_country("germany", out, COUNTRY_LEN);
    check("country_fallback: \"germany\" -> \"Germany\"",
          strcmp(out, "Germany") == 0, out, "Germany");

    normalize_country("JAPAN", out, COUNTRY_LEN);
    check("country_fallback: \"JAPAN\" -> \"Japan\"",
          strcmp(out, "Japan") == 0, out, "Japan");

    normalize_country("australia", out, COUNTRY_LEN);
    check("country_fallback: \"australia\" -> \"Australia\"",
          strcmp(out, "Australia") == 0, out, "Australia");

    normalize_country("france", out, COUNTRY_LEN);
    check("country_fallback: \"france\" -> \"France\"",
          strcmp(out, "France") == 0, out, "France");

    normalize_country("NETHERLANDS", out, COUNTRY_LEN);
    check("country_fallback: \"NETHERLANDS\" -> \"Netherlands\"",
          strcmp(out, "Netherlands") == 0, out, "Netherlands");
}

/* ------------------------------------------------------------------ */
/*  7.  Abbreviation expansion                                         */
/* ------------------------------------------------------------------ */

static void test_abbreviations(void)
{
    char out[NAME_LEN];

    normalize_name("univ", out, NAME_LEN);
    check("abbrev: \"univ\" -> \"University\"",
          strcmp(out, "University") == 0, out, "University");

    normalize_name("UNIV", out, NAME_LEN);
    check("abbrev: \"UNIV\" (uppercase) -> \"University\"",
          strcmp(out, "University") == 0, out, "University");

    normalize_name("inst", out, NAME_LEN);
    check("abbrev: \"inst\" -> \"Institute\"",
          strcmp(out, "Institute") == 0, out, "Institute");

    normalize_name("tech", out, NAME_LEN);
    check("abbrev: \"tech\" -> \"Tech\" (不展開，Fix G)",
          strcmp(out, "Tech") == 0, out, "Tech");

    normalize_name("TECH", out, NAME_LEN);
    check("abbrev: \"TECH\" -> \"Tech\" (不展開，Fix G)",
          strcmp(out, "Tech") == 0, out, "Tech");

    normalize_name("univ.", out, NAME_LEN);
    check("abbrev: \"univ.\" -> \"University\"",
          strcmp(out, "University") == 0, out, "University");

    normalize_name("univ inst tech", out, NAME_LEN);
    check("abbrev: multiple in one name (Fix G: tech 不展開)",
          strcmp(out, "University Institute Tech") == 0,
          out, "University Institute Tech");

    normalize_name("MIT univ", out, NAME_LEN);
    check("abbrev: MIT univ -> \"MIT University\"",
          strcmp(out, "MIT University") == 0, out, "MIT University");
}

/* ------------------------------------------------------------------ */
/*  8.  Idempotency                                                    */
/* ------------------------------------------------------------------ */

static void test_idempotency(void)
{
    static const char *names[] = {
        "University of California Berkeley",
        "MIT",
        "Massachusetts Institute of Technology",
        "U.C. Berkeley",
        "univ of tech",
        "EPFL",
        "KAIST",
        "Al-Azhar University",
        "King's College London",
        NULL
    };

    for (int i = 0; names[i]; i++) {
        char out1[NAME_LEN], out2[NAME_LEN];
        char label[300];

        normalize_name(names[i], out1, NAME_LEN);
        normalize_name(out1,     out2, NAME_LEN);
        snprintf(label, sizeof(label),
                 "idempotent_name: \"%s\"", names[i]);
        check(label, strcmp(out1, out2) == 0, out2, out1);
    }

    static const char *countries[] = {
        "usa", "United States", "uk", "UK",
        "Germany", "germany",
        "china", "China (Mainland)",
        "hong kong", "Hong Kong SAR",
        "Taiwan", "south korea",
        NULL
    };

    for (int i = 0; countries[i]; i++) {
        char c1[COUNTRY_LEN], c2[COUNTRY_LEN];
        char label[200];

        normalize_country(countries[i], c1, COUNTRY_LEN);
        normalize_country(c1,           c2, COUNTRY_LEN);
        snprintf(label, sizeof(label),
                 "idempotent_country: \"%s\"", countries[i]);
        check(label, strcmp(c1, c2) == 0, c2, c1);
    }
}

/* ------------------------------------------------------------------ */
/*  9.  Rank edge cases                                                */
/* ------------------------------------------------------------------ */

static void test_rank_edge_cases(void)
{
    int mn, mx;

    parse_rank("0", &mn, &mx);
    check("rank: \"0\" -> 0/0", mn == 0 && mx == 0, NULL, NULL);

    parse_rank("999999", &mn, &mx);
    check("rank: \"999999\" -> 999999/999999",
          mn == 999999 && mx == 999999, NULL, NULL);

    parse_rank("abc", &mn, &mx);
    check("rank: \"abc\" -> -1/-1", mn == -1 && mx == -1, NULL, NULL);

    /* UTF-8 en-dash U+2013 = 0xE2 0x80 0x93 */
    parse_rank("201\xe2\x80\x93" "250", &mn, &mx);
    check("rank: en-dash \"201-250\" -> 201/250",
          mn == 201 && mx == 250, NULL, NULL);

    /* UTF-8 em-dash U+2014 = 0xE2 0x80 0x94 */
    parse_rank("301\xe2\x80\x94" "350", &mn, &mx);
    check("rank: em-dash \"301-350\" -> 301/350",
          mn == 301 && mx == 350, NULL, NULL);

    parse_rank("150-101", &mn, &mx);
    check("rank: inverted range 150-101 parsed without crash",
          mn == 101 && mx == 150, NULL, NULL);  /* Fix Q: auto-swapped */

    parse_rank("Top 0", &mn, &mx);
    check("rank: \"Top 0\" -> -1/-1",
          mn == -1 && mx == -1, NULL, NULL);  /* Fix P: rejected */

    parse_rank("1-2-3", &mn, &mx);
    check("rank: \"1-2-3\" -> 1/2",
          mn == 1 && mx == 2, NULL, NULL);

    parse_rank("Rank 53", &mn, &mx);
    check("rank: \"Rank 53\" -> 53/53", mn == 53 && mx == 53, NULL, NULL);

    parse_rank("rank 100", &mn, &mx);
    check("rank: \"rank 100\" (lowercase) -> 100/100",
          mn == 100 && mx == 100, NULL, NULL);

    parse_rank("Top 100", &mn, &mx);
    check("rank: \"Top 100\" -> 1/100", mn == 1 && mx == 100, NULL, NULL);

    parse_rank("top 50", &mn, &mx);
    check("rank: \"top 50\" (lowercase) -> 1/50",
          mn == 1 && mx == 50, NULL, NULL);

    parse_rank("  42  ", &mn, &mx);
    check("rank: \"  42  \" -> 42/42", mn == 42 && mx == 42, NULL, NULL);
}

/* ------------------------------------------------------------------ */
/*  10. Score edge cases                                               */
/* ------------------------------------------------------------------ */

static void test_score_edge_cases(void)
{
    double s;

#define NEAR(v, target) ((v) > (target) - 0.001 && (v) < (target) + 0.001)

    s = parse_score("0");
    check("score: \"0\" -> 0.0", NEAR(s, 0.0), NULL, NULL);

    s = parse_score("0.0");
    check("score: \"0.0\" -> 0.0", NEAR(s, 0.0), NULL, NULL);

    s = parse_score("100.0");
    check("score: \"100.0\" -> 100.0", NEAR(s, 100.0), NULL, NULL);

    s = parse_score("NaN");
    check("score: \"NaN\" -> -1.0 (no numeric prefix)",
          NEAR(s, -1.0), NULL, NULL);

    s = parse_score("Inf");
    check("score: \"Inf\" -> -1.0 (no numeric prefix)",
          NEAR(s, -1.0), NULL, NULL);

    s = parse_score("+50.5");
    check("score: \"+50.5\" -> 50.5", NEAR(s, 50.5), NULL, NULL);

    s = parse_score("999999.99");
    check("score: \"999999.99\" -> large value", s > 999999.0, NULL, NULL);

    s = parse_score("  85.5  ");
    check("score: leading spaces \"  85.5  \" -> 85.5",
          NEAR(s, 85.5), NULL, NULL);

    s = parse_score("-1.0");
    check("score: \"-1.0\" returns -1.0 (ambiguous but consistent)",
          NEAR(s, -1.0), NULL, NULL);

    s = parse_score("Score: 91.25");
    check("score: labeled \"Score: 91.25\" -> 91.25",
          NEAR(s, 91.25), NULL, NULL);

    s = parse_score("abc");
    check("score: \"abc\" -> -1.0", NEAR(s, -1.0), NULL, NULL);

#undef NEAR
}

/* ------------------------------------------------------------------ */
/*  11. Name normalization edge cases                                  */
/* ------------------------------------------------------------------ */

static void test_name_edge_cases(void)
{
    char out[NAME_LEN];

    normalize_name("...", out, NAME_LEN);
    check("name_edge: \"...\" -> \"\"",
          strcmp(out, "") == 0, out, "");

    normalize_name(",,,", out, NAME_LEN);
    check("name_edge: \",,,\" -> \"\"",
          strcmp(out, "") == 0, out, "");

    normalize_name("Al-Azhar University", out, NAME_LEN);
    check("name_edge: \"Al-Azhar University\" preserved",
          strcmp(out, "Al-Azhar University") == 0,
          out, "Al-Azhar University");

    normalize_name("University of California Berkeley (UCB)", out, NAME_LEN);
    check("name_edge: parenthetical \"(UCB)\" stays uppercase",
          strcmp(out, "University of California Berkeley (UCB)") == 0,
          out, "University of California Berkeley (UCB)");

    normalize_name("(MIT)", out, NAME_LEN);
    check("name_edge: \"(MIT)\" standalone -> \"(MIT)\"",
          strcmp(out, "(MIT)") == 0, out, "(MIT)");

    normalize_name("EPFL", out, NAME_LEN);
    check("name_edge: \"EPFL\" stays uppercase",
          strcmp(out, "EPFL") == 0, out, "EPFL");

    normalize_name("KAIST", out, NAME_LEN);
    check("name_edge: \"KAIST\" stays uppercase",
          strcmp(out, "KAIST") == 0, out, "KAIST");

    normalize_name("POSTECH", out, NAME_LEN);
    check("name_edge: \"POSTECH\" stays uppercase",
          strcmp(out, "POSTECH") == 0, out, "POSTECH");

    normalize_name("LSE", out, NAME_LEN);
    check("name_edge: \"LSE\" stays uppercase",
          strcmp(out, "LSE") == 0, out, "LSE");

    normalize_name("university of the arts london", out, NAME_LEN);
    check("name_edge: connectors lowercase in middle",
          strcmp(out, "University of the Arts London") == 0,
          out, "University of the Arts London");

    normalize_name("mAssAchUsEtTs InStItUtE oF tEcHnOlOgY", out, NAME_LEN);
    check("name_edge: random-case input normalised correctly",
          strcmp(out, "Massachusetts Institute of Technology") == 0,
          out, "Massachusetts Institute of Technology");

    normalize_name("King's College London", out, NAME_LEN);
    check("name_edge: apostrophe in \"King's\" preserved",
          strcmp(out, "King's College London") == 0,
          out, "King's College London");

    normalize_name("University: Cambridge", out, NAME_LEN);
    check("name_edge: colon -> space -> \"University Cambridge\"",
          strcmp(out, "University Cambridge") == 0,
          out, "University Cambridge");
}

/* ------------------------------------------------------------------ */
/*  12. Throughput — 10 000 records                                    */
/* ------------------------------------------------------------------ */

static void test_throughput(void)
{
    const int         N         = 10000;
    const char *const test_file = "build/test_throughput.csv";

    UniversityRecord *records;
    int               count;
    clock_t           t0, t1;
    double            elapsed;

    records = (UniversityRecord *)malloc((size_t)N * sizeof(UniversityRecord));
    if (!records) {
        check("throughput: malloc for 10 000 records", 0, NULL, NULL);
        return;
    }

    FILE *fp = fopen(test_file, "w");
    if (!fp) {
        free(records);
        check("throughput: create test CSV file", 0, NULL, NULL);
        return;
    }
    fprintf(fp, "University,Country,Rank Min,Rank Max,Overall Score\n");
    for (int i = 0; i < N; i++) {
        static const char *country = (void *)0;
        country = (i % 5 == 0) ? "usa"   :
                  (i % 5 == 1) ? "uk"    :
                  (i % 5 == 2) ? "sg"    :
                  (i % 5 == 3) ? "china" : "germany";
        fprintf(fp,
                "univ of Technology and Science %d,%s,%d,%d,%.2f\n",
                i + 1, country, i + 1, i + 1, 40.0 + (double)(i % 60));
    }
    fclose(fp);

    t0    = clock();
    count = load_csv_data(test_file, records, N);
    if (count > 0) {
        for (int i = 0; i < count; i++)
            normalize_record(&records[i]);
    }
    t1      = clock();
    elapsed = (double)(t1 - t0) / CLOCKS_PER_SEC;

    printf("       throughput: %d records in %.3f s\n", count, elapsed);

    check("throughput: all 10 000 records processed",
          count == N, NULL, NULL);
    check("throughput: completed in < 5 seconds",
          elapsed < 5.0, NULL, NULL);

    if (count > 0) {
        check("throughput: first record country normalised",
              strcmp(records[0].normalized_country, "United States") == 0,
              records[0].normalized_country, "United States");
        check("throughput: last record country normalised",
              strlen(records[count - 1].normalized_country) > 0,
              NULL, NULL);
    }

    remove(test_file);
    free(records);
}

/* ------------------------------------------------------------------ */
/*  main                                                               */
/* ------------------------------------------------------------------ */

int main(void)
{
    printf("==== EXTREME STRESS & EDGE-CASE TESTS ====\n\n");

    printf("--- 1. NULL / Empty Safety ---\n");
    test_null_safety();
    test_empty_string();
    test_whitespace_only();

    printf("\n--- 2. Single Character ---\n");
    test_single_char();

    printf("\n--- 3. Buffer Boundary ---\n");
    test_buffer_boundary();

    printf("\n--- 4. Unicode / Multi-byte ---\n");
    test_unicode();

    printf("\n--- 5. Adversarial Inputs ---\n");
    test_adversarial();

    printf("\n--- 6. Country Alias Exhaustion ---\n");
    test_country_aliases();

    printf("\n--- 7. Abbreviation Expansion ---\n");
    test_abbreviations();

    printf("\n--- 8. Idempotency ---\n");
    test_idempotency();

    printf("\n--- 9. Rank Edge Cases ---\n");
    test_rank_edge_cases();

    printf("\n--- 10. Score Edge Cases ---\n");
    test_score_edge_cases();

    printf("\n--- 11. Name Edge Cases ---\n");
    test_name_edge_cases();

    printf("\n--- 12. Throughput (10 000 records) ---\n");
    test_throughput();

    printf("\n==== EXTREME TEST SUMMARY ====\n");
    printf("Passed: %d / %d\n", g_tests_passed, g_tests_run);
    if (g_tests_failed > 0) {
        printf("FAILED: %d test(s)\n", g_tests_failed);
        return 1;
    }
    printf("All extreme tests passed.\n");
    return 0;
}
