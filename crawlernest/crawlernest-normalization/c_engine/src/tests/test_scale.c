/*
 * test_scale.c
 *
 * Production-scale stress tests for the Clawer C Data Normalization Engine.
 *
 * Motivation: real deployments deal with thousands to hundreds-of-thousands
 * of university records. These tests confirm correctness, performance, and
 * resilience do not degrade at that scale.
 *
 * Test categories:
 *  1.  100 000-record throughput
 *  2.  Max-field-length bulk (5 000 records at NAME_LEN / COUNTRY_LEN limits)
 *  3.  Dirty bulk data  (10 000 rows, 10 % malformed — must load 9 000 clean)
 *  4.  CSV round-trip at scale (1 000 records: write → read → re-normalize)
 *  5.  Normalization consistency (same 20 inputs × 500 reps = 10 000 calls)
 *  6.  All rank formats at scale (10 000 records cycling 5 format types)
 *  7.  All country aliases at scale (10 000 records cycling every alias)
 *  8.  CSV line-length boundary (lines near / over the 1 024-byte fgets limit)
 *  9.  Idempotency at scale (2 000 records normalized twice)
 * 10.  Large-file write-then-read integrity (50 000 records round-trip)
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

static int g_run = 0, g_pass = 0, g_fail = 0;

static void chk(const char *label, int ok,
                const char *actual, const char *expect)
{
    g_run++;
    if (ok) {
        g_pass++;
        printf("[PASS] %s\n", label);
    } else {
        g_fail++;
        printf("[FAIL] %s\n", label);
        if (actual && expect)
            printf("       expected: \"%s\"\n       actual:   \"%s\"\n",
                   expect, actual);
    }
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

/* Write a plain text file, return 1 on success. */
static int write_file(const char *path, const char *content)
{
    FILE *fp = fopen(path, "w");
    if (!fp) return 0;
    fputs(content, fp);
    return fclose(fp) == 0;
}

/* ------------------------------------------------------------------ */
/*  1.  100 000-record throughput                                      */
/* ------------------------------------------------------------------ */

static void test_100k_throughput(void)
{
    const int   N    = 100000;
    const char *path = "build/test_scale_100k.csv";

    UniversityRecord *recs;
    int    count;
    clock_t t0, t1;
    double  elapsed;

    recs = (UniversityRecord *)malloc((size_t)N * sizeof(UniversityRecord));
    if (!recs) { chk("100k: malloc", 0, NULL, NULL); return; }

    /* Generate CSV */
    FILE *fp = fopen(path, "w");
    if (!fp) { free(recs); chk("100k: create file", 0, NULL, NULL); return; }

    fprintf(fp, "University,Country,Rank Min,Rank Max,Overall Score\n");
    for (int i = 0; i < N; i++) {
        /* Cycle through country aliases and rank/score varieties */
        static const char *countries[] = {
            "usa","uk","sg","china","germany","japan","australia",
            "france","korea","taiwan"
        };
        int rank = (i % 500) + 1;
        fprintf(fp,
                "univ of Technology and Science %d,%s,%d,%d,%.2f\n",
                i + 1,
                countries[i % 10],
                rank, rank,
                40.0 + (double)(i % 60));
    }
    fclose(fp);

    t0 = clock();
    count = load_csv_data(path, recs, N);
    if (count > 0)
        for (int i = 0; i < count; i++)
            normalize_record(&recs[i]);
    t1      = clock();
    elapsed = (double)(t1 - t0) / CLOCKS_PER_SEC;

    printf("       100k: %d records in %.3f s  (%.0f rec/s)\n",
           count, elapsed, count / (elapsed > 0 ? elapsed : 1));

    chk("100k: all records loaded",    count == N, NULL, NULL);
    chk("100k: completed < 10 s",      elapsed < 10.0, NULL, NULL);
    chk("100k: first name normalised",
        strlen(recs[0].normalized_name) > 0, NULL, NULL);
    chk("100k: last country normalised",
        strlen(recs[N - 1].normalized_country) > 0, NULL, NULL);

    remove(path);
    free(recs);
}

/* ------------------------------------------------------------------ */
/*  2.  Max-field-length bulk                                          */
/* ------------------------------------------------------------------ */

static void test_max_field_bulk(void)
{
    const int   N    = 5000;
    const char *path = "build/test_scale_maxfield.csv";

    UniversityRecord *recs;
    int count;

    recs = (UniversityRecord *)malloc((size_t)N * sizeof(UniversityRecord));
    if (!recs) { chk("maxfield: malloc", 0, NULL, NULL); return; }

    /* Name field: fill to NAME_LEN-1 = 149 chars of 'A' + spaces so
     * normalization does not collapse everything to one letter.
     * Pattern: "Aaa Aaa Aaa ..." repeated to fill 149 chars.            */
    char long_name[NAME_LEN];               /* 150 bytes */
    for (int i = 0; i < NAME_LEN - 1; i++)
        long_name[i] = (i % 4 == 3) ? ' ' : 'a'; /* "aaa aaa aaa ..." */
    long_name[NAME_LEN - 1] = '\0';

    /* Country field: fill to COUNTRY_LEN-1 = 79 chars — unmapped, falls back
     * to title case                                                       */
    char long_country[COUNTRY_LEN];         /* 80 bytes */
    for (int i = 0; i < COUNTRY_LEN - 1; i++)
        long_country[i] = (i % 6 == 5) ? ' ' : 'b';
    long_country[COUNTRY_LEN - 1] = '\0';

    FILE *fp = fopen(path, "w");
    if (!fp) { free(recs); chk("maxfield: create file", 0, NULL, NULL); return; }

    fprintf(fp, "University,Country,Rank Min,Rank Max,Overall Score\n");
    for (int i = 0; i < N; i++)
        fprintf(fp, "%s,%s,%d,%d,%.2f\n",
                long_name, long_country, i + 1, i + 1, 50.0 + (i % 50));
    fclose(fp);

    count = load_csv_data(path, recs, N);
    for (int i = 0; i < count; i++)
        normalize_record(&recs[i]);

    chk("maxfield: all records loaded", count == N, NULL, NULL);

    /* Every normalized name must fit within NAME_LEN */
    int all_fit = 1;
    for (int i = 0; i < count; i++)
        if ((int)strlen(recs[i].normalized_name) >= NAME_LEN) { all_fit = 0; break; }
    chk("maxfield: all normalized names within NAME_LEN", all_fit, NULL, NULL);

    /* Every normalized country must fit within COUNTRY_LEN */
    int all_c_fit = 1;
    for (int i = 0; i < count; i++)
        if ((int)strlen(recs[i].normalized_country) >= COUNTRY_LEN) { all_c_fit = 0; break; }
    chk("maxfield: all normalized countries within COUNTRY_LEN", all_c_fit, NULL, NULL);

    remove(path);
    free(recs);
}

/* ------------------------------------------------------------------ */
/*  3.  Dirty bulk data (10 % malformed rows)                          */
/* ------------------------------------------------------------------ */

static void test_dirty_bulk(void)
{
    const int TOTAL   = 10000;
    const int GOOD    = 9000;   /* every i where i % 10 != 0 */
    const int path_sz = 64;
    char path[64];
    snprintf(path, (size_t)path_sz, "build/test_scale_dirty.csv");

    UniversityRecord *recs;
    int count;

    recs = (UniversityRecord *)malloc((size_t)(GOOD + 10) * sizeof(UniversityRecord));
    if (!recs) { chk("dirty: malloc", 0, NULL, NULL); return; }

    FILE *fp = fopen(path, "w");
    if (!fp) { free(recs); chk("dirty: create file", 0, NULL, NULL); return; }

    fprintf(fp, "University,Country,Rank Min,Rank Max,Overall Score\n");
    for (int i = 0; i < TOTAL; i++) {
        if (i % 10 == 0) {
            /* Malformed row — cycle through three error types */
            switch (i % 30) {
                case 0:
                    /* Unterminated quoted field */
                    fprintf(fp, "\"Unterminated Row %d,usa,1,1,90.0\n", i);
                    break;
                case 10:
                    /* Too few fields (only 4 columns) */
                    fprintf(fp, "Short Row %d,usa,1,90.0\n", i);
                    break;
                default:
                    /* Too many fields (6 columns) */
                    fprintf(fp, "Long Row %d,usa,1,1,90.0,extra\n", i);
                    break;
            }
        } else {
            fprintf(fp, "University %d,usa,%d,%d,%.2f\n",
                    i, i, i, 50.0 + (i % 50));
        }
    }
    fclose(fp);

    count = load_csv_data(path, recs, GOOD + 10);

    chk("dirty: exactly 9 000 good records loaded",
        count == GOOD, NULL, NULL);
    chk("dirty: no crash on mixed valid/invalid data", 1, NULL, NULL);

    /* Spot-check: every loaded record's normalized name is non-empty */
    int norm_ok = 1;
    for (int i = 0; i < count; i++) {
        normalize_record(&recs[i]);
        if (strlen(recs[i].normalized_name) == 0) { norm_ok = 0; break; }
    }
    chk("dirty: all good records normalise without empty name", norm_ok, NULL, NULL);

    remove(path);
    free(recs);
}

/* ------------------------------------------------------------------ */
/*  4.  CSV round-trip at scale                                        */
/* ------------------------------------------------------------------ */

static void test_round_trip_scale(void)
{
    const int   N     = 1000;
    const char *path1 = "build/test_scale_rt1.csv";
    const char *path2 = "build/test_scale_rt2.csv";

    UniversityRecord *recs1;
    UniversityRecord *recs2;

    recs1 = (UniversityRecord *)malloc((size_t)N * sizeof(UniversityRecord));
    recs2 = (UniversityRecord *)malloc((size_t)N * sizeof(UniversityRecord));
    if (!recs1 || !recs2) {
        free(recs1); free(recs2);
        chk("round_trip: malloc", 0, NULL, NULL);
        return;
    }

    /* Build raw CSV and normalise */
    FILE *fp = fopen(path1, "w");
    if (!fp) {
        free(recs1); free(recs2);
        chk("round_trip: create file", 0, NULL, NULL);
        return;
    }

    /* Use diverse raw inputs: apostrophes, hyphens, abbrevs, unicode mix */
    static const char *raw_names[] = {
        "univ of Tech",
        "Al-Azhar Univ",
        "Institut de Science",
        "MIT",
        "KAIST",
        "LSE",
        "University of the Arts London",
        "King's College",
        "NUS",
        "UNSW"
    };
    static const char *raw_countries[] = {
        "usa","uk","france","usa","korea",
        "uk","uk","uk","sg","australia"
    };

    fprintf(fp, "University,Country,Rank Min,Rank Max,Overall Score\n");
    for (int i = 0; i < N; i++) {
        int idx = i % 10;
        fprintf(fp, "%s,%s,%d,%d,%.2f\n",
                raw_names[idx], raw_countries[idx],
                i + 1, i + 1, 60.0 + (i % 40));
    }
    fclose(fp);

    /* First load + normalise */
    int c1 = load_csv_data(path1, recs1, N);
    for (int i = 0; i < c1; i++) normalize_record(&recs1[i]);

    /* Write normalised records to second file */
    write_normalized_csv(path2, recs1, c1);

    /* Read back and re-normalise */
    int c2 = load_csv_data(path2, recs2, N);
    for (int i = 0; i < c2; i++) normalize_record(&recs2[i]);

    chk("round_trip: both loads return same count",
        c1 == N && c2 == c1, NULL, NULL);

    /* After idempotent round-trip: second normalize == first normalize */
    int names_match = 1, countries_match = 1, scores_match = 1;
    for (int i = 0; i < c1 && i < c2; i++) {
        if (strcmp(recs1[i].normalized_name,    recs2[i].normalized_name)    != 0) names_match    = 0;
        if (strcmp(recs1[i].normalized_country, recs2[i].normalized_country) != 0) countries_match = 0;
        if (recs1[i].rank_min != recs2[i].rank_min ||
            recs1[i].rank_max != recs2[i].rank_max)                                scores_match   = 0;
    }
    chk("round_trip: normalized names stable after write→read",
        names_match, NULL, NULL);
    chk("round_trip: normalized countries stable after write→read",
        countries_match, NULL, NULL);
    chk("round_trip: ranks stable after write→read",
        scores_match, NULL, NULL);

    remove(path1); remove(path2);
    free(recs1);   free(recs2);
}

/* ------------------------------------------------------------------ */
/*  5.  Normalization consistency (same inputs, many repetitions)      */
/* ------------------------------------------------------------------ */

static void test_consistency(void)
{
    static const char *names[] = {
        "univ of technology",
        "Massachusetts Inst of Tech",
        "U.C. Berkeley",
        "KAIST",
        "EPFL",
        "Al-Azhar Univ",
        "King's College, London",
        "NUS",
        "LSE",
        "École Polytechnique",
        "UNSW",
        "inst of science and tech",
        "MIT",
        "Univ of the Arts London",
        "National Univ of Singapore",
        NULL
    };
    static const char *countries[] = {
        "usa","uk","sg","china","korea",
        "taiwan","hong kong","australia","germany","france",
        "japan","usa","uk","sg","china",
        NULL
    };

    /* Capture reference normalisation on the first pass */
    int n = 0;
    while (names[n]) n++;

    char ref_name[32][NAME_LEN];
    char ref_country[32][COUNTRY_LEN];

    for (int i = 0; i < n; i++) {
        normalize_name(names[i],       ref_name[i],    NAME_LEN);
        normalize_country(countries[i], ref_country[i], COUNTRY_LEN);
    }

    /* Repeat 500 more times and verify identical output every time */
    const int REPS = 500;
    int name_drift    = 0;
    int country_drift = 0;

    for (int rep = 0; rep < REPS; rep++) {
        char out_n[NAME_LEN];
        char out_c[COUNTRY_LEN];
        for (int i = 0; i < n; i++) {
            normalize_name(names[i],        out_n, NAME_LEN);
            normalize_country(countries[i], out_c, COUNTRY_LEN);
            if (strcmp(out_n, ref_name[i])    != 0) name_drift++;
            if (strcmp(out_c, ref_country[i]) != 0) country_drift++;
        }
    }

    printf("       consistency: %d × %d = %d total normalisations\n",
           REPS + 1, n, (REPS + 1) * n);

    chk("consistency: normalize_name produces identical output across 500+ repetitions",
        name_drift == 0, NULL, NULL);
    chk("consistency: normalize_country identical across 500+ repetitions",
        country_drift == 0, NULL, NULL);
}

/* ------------------------------------------------------------------ */
/*  6.  All rank formats at scale                                      */
/* ------------------------------------------------------------------ */

static void test_rank_format_scale(void)
{
    const int   N    = 10000;
    const char *path = "build/test_scale_rank.csv";

    UniversityRecord *recs;

    recs = (UniversityRecord *)malloc((size_t)N * sizeof(UniversityRecord));
    if (!recs) { chk("rank_scale: malloc", 0, NULL, NULL); return; }

    FILE *fp = fopen(path, "w");
    if (!fp) { free(recs); chk("rank_scale: create file", 0, NULL, NULL); return; }

    fprintf(fp, "University,Country,Rank Min,Rank Max,Overall Score\n");
    for (int i = 0; i < N; i++) {
        int r = (i % 500) + 1;
        switch (i % 5) {
            case 0: fprintf(fp, "Univ %d,usa,%d,%d,80.0\n",    i, r, r);       break;
            case 1: fprintf(fp, "Univ %d,usa,%d,%d,80.0\n",    i, r, r + 49);  break;
            case 2: fprintf(fp, "Univ %d,usa,%d,%d,80.0\n",    i, 1, r);       break;
            case 3: fprintf(fp, "Univ %d,usa,%d,%d,80.0\n",    i, r, r);       break;
            case 4: fprintf(fp, "Univ %d,usa,%d,%d,80.0\n",    i, r, r + 99);  break;
        }
    }
    fclose(fp);

    int count = load_csv_data(path, recs, N);
    chk("rank_scale: all records loaded", count == N, NULL, NULL);

    int all_ok = 1;
    for (int i = 0; i < count; i++) {
        normalize_record(&recs[i]);
        /* rank_min must always be >= 1 (all ranks positive) */
        if (recs[i].rank_min < 1) { all_ok = 0; break; }
    }
    chk("rank_scale: all ranks parsed to positive values", all_ok, NULL, NULL);

    remove(path);
    free(recs);
}

/* ------------------------------------------------------------------ */
/*  7.  All country aliases at scale                                   */
/* ------------------------------------------------------------------ */

static void test_country_scale(void)
{
    const int   N    = 10000;
    const char *path = "build/test_scale_country.csv";

    /* 38 aliases spread across N records */
    static const char *aliases[] = {
        "usa","USA","us","U.S.A.","united states","united states of america",
        "uk","UK","u.k.","united kingdom","great britain","britain",
        "england","scotland","wales","northern ireland",
        "sg","SG","singapore",
        "china","China","mainland china","china mainland","prc",
        "peoples republic of china",
        "hong kong","hong kong sar",
        "taiwan","roc","ROC","republic of china",
        "south korea","korea","Korea","republic of korea",
        "germany","japan","australia",
        NULL
    };
    static const char *canonical[] = {
        "United States","United States","United States","United States",
        "United States","United States",
        "United Kingdom","United Kingdom","United Kingdom","United Kingdom",
        "United Kingdom","United Kingdom",
        "United Kingdom","United Kingdom","United Kingdom","United Kingdom",
        "Singapore","Singapore","Singapore",
        "China (Mainland)","China (Mainland)","China (Mainland)",
        "China (Mainland)","China (Mainland)","China (Mainland)",
        "Hong Kong SAR","Hong Kong SAR",
        "Taiwan","Taiwan","Taiwan","Taiwan",
        "South Korea","South Korea","South Korea","South Korea",
        "Germany","Japan","Australia",
        NULL
    };

    int n_aliases = 0;
    while (aliases[n_aliases]) n_aliases++;

    UniversityRecord *recs;
    recs = (UniversityRecord *)malloc((size_t)N * sizeof(UniversityRecord));
    if (!recs) { chk("country_scale: malloc", 0, NULL, NULL); return; }

    FILE *fp = fopen(path, "w");
    if (!fp) { free(recs); chk("country_scale: create file", 0, NULL, NULL); return; }

    fprintf(fp, "University,Country,Rank Min,Rank Max,Overall Score\n");
    for (int i = 0; i < N; i++)
        fprintf(fp, "Univ %d,%s,%d,%d,80.0\n",
                i, aliases[i % n_aliases], i + 1, i + 1);
    fclose(fp);

    int count = load_csv_data(path, recs, N);
    chk("country_scale: all records loaded", count == N, NULL, NULL);

    int all_ok = 1;
    for (int i = 0; i < count; i++) {
        normalize_record(&recs[i]);
        const char *want = canonical[i % n_aliases];
        if (strcmp(recs[i].normalized_country, want) != 0) {
            all_ok = 0;
            printf("       MISMATCH at i=%d: alias=\"%s\" got=\"%s\" want=\"%s\"\n",
                   i, aliases[i % n_aliases],
                   recs[i].normalized_country, want);
            break;
        }
    }
    chk("country_scale: every alias normalises to correct canonical at 10k scale",
        all_ok, NULL, NULL);

    remove(path);
    free(recs);
}

/* ------------------------------------------------------------------ */
/*  8.  CSV line-length boundary                                       */
/* ------------------------------------------------------------------ */

static void test_line_boundary(void)
{
    /* CSV_LINE_LEN = 1024.  fgets reads at most 1023 chars per call.
     *
     * Scenario A: line < 1023 chars → fits in one fgets call → OK
     * Scenario B: line ≥ 1024 chars → split across 2+ fgets calls
     *             → each fragment parsed as an invalid row → skipped
     *             → valid rows before/after still loaded correctly
     */

    const char *path = "build/test_scale_linelen.csv";

    /* --- Scenario A: 900-char name field (triggers CSV_PARSE_FIELD_TOO_LONG)
     *     but the TOTAL line fits in fgets buffer (< 1024 chars).
     *     Even though the field is too long, the row is rejected cleanly.    */
    {
        char buf[2048];
        int  pos = 0;

        /* Header */
        pos += snprintf(buf + pos, sizeof(buf) - (size_t)pos,
                        "University,Country,Rank Min,Rank Max,Overall Score\n");
        /* Valid row before */
        pos += snprintf(buf + pos, sizeof(buf) - (size_t)pos,
                        "MIT,usa,1,1,99.0\n");
        /* Row with 260-char name (> CSV_FIELD_LEN-1=255) but total < 1024 */
        pos += snprintf(buf + pos, sizeof(buf) - (size_t)pos, "\"");
        for (int i = 0; i < 260 && pos < (int)sizeof(buf) - 2; i++)
            buf[pos++] = 'A';
        pos += snprintf(buf + pos, sizeof(buf) - (size_t)pos,
                        "\",usa,1,1,80.0\n");
        /* Valid row after */
        pos += snprintf(buf + pos, sizeof(buf) - (size_t)pos,
                        "Stanford,usa,2,2,98.0\n");
        buf[pos] = '\0';

        if (write_file(path, buf)) {
            UniversityRecord recs[4];
            int count = load_csv_data(path, recs, 4);
            /* MIT and Stanford loaded; 260-char-name row skipped */
            chk("line_boundary: field-too-long row skipped, flanking rows OK",
                count == 2 &&
                strcmp(recs[0].raw_name, "MIT")      == 0 &&
                strcmp(recs[1].raw_name, "Stanford") == 0,
                NULL, NULL);
        }
        remove(path);
    }

    /* --- Scenario B: total line > 1023 chars (fgets truncation)
     *     Build a line where 5 fields together exceed 1024 bytes.
     *     Each field is padded to 210 chars: 5×210 + 4 commas + \n = 1055 chars.
     *     The fgets buffer (1023) cuts the line mid-way; both halves produce
     *     wrong field counts and are skipped.  Flanking valid rows must survive. */
    {
        /* Write CSV into a real file using fprintf for large content */
        FILE *fp = fopen(path, "w");
        if (fp) {
            /* Header */
            fprintf(fp, "University,Country,Rank Min,Rank Max,Overall Score\n");
            /* Valid row before the long line */
            fprintf(fp, "MIT,usa,1,1,99.0\n");

            /* Long row: 5 fields × 210 chars = 1050 + 4 + \n = 1055 chars total */
            for (int col = 0; col < 5; col++) {
                for (int c = 0; c < 210; c++) fputc('X', fp);
                if (col < 4) fputc(',', fp);
            }
            fputc('\n', fp);

            /* Valid row after the long line */
            fprintf(fp, "Stanford,usa,2,2,98.0\n");
            fclose(fp);

            UniversityRecord recs[4];
            int count = load_csv_data(path, recs, 4);
            chk("line_boundary: line > 1024 bytes split/skipped, flanking rows OK",
                count == 2 &&
                strcmp(recs[0].raw_name, "MIT")      == 0 &&
                strcmp(recs[1].raw_name, "Stanford") == 0,
                NULL, NULL);
        }
        remove(path);
    }

    /* --- Scenario C: 100 rows, every 5th has a line > 1023 chars.
     *     Expect 80 good records loaded, no crash.                           */
    {
        const int TOTAL = 100;
        const int GOOD  = 80;

        FILE *fp = fopen(path, "w");
        if (fp) {
            fprintf(fp, "University,Country,Rank Min,Rank Max,Overall Score\n");
            for (int i = 0; i < TOTAL; i++) {
                if (i % 5 == 0) {
                    /* Very long line */
                    for (int col = 0; col < 5; col++) {
                        for (int c = 0; c < 210; c++) fputc('X', fp);
                        if (col < 4) fputc(',', fp);
                    }
                    fputc('\n', fp);
                } else {
                    fprintf(fp, "Univ %d,usa,%d,%d,80.0\n", i, i + 1, i + 1);
                }
            }
            fclose(fp);

            UniversityRecord *recs = (UniversityRecord *)malloc(
                (size_t)(GOOD + 10) * sizeof(UniversityRecord));
            if (recs) {
                int count = load_csv_data(path, recs, GOOD + 10);
                chk("line_boundary: 80/100 good rows survive long-line interspersing",
                    count == GOOD, NULL, NULL);
                free(recs);
            }
        }
        remove(path);
    }
}

/* ------------------------------------------------------------------ */
/*  9.  Idempotency at scale                                           */
/* ------------------------------------------------------------------ */

static void test_idempotency_scale(void)
{
    const int   N    = 2000;
    const char *path = "build/test_scale_idempotent.csv";

    UniversityRecord *recs1;
    UniversityRecord *recs2;

    recs1 = (UniversityRecord *)malloc((size_t)N * sizeof(UniversityRecord));
    recs2 = (UniversityRecord *)malloc((size_t)N * sizeof(UniversityRecord));
    if (!recs1 || !recs2) {
        free(recs1); free(recs2);
        chk("idempotent_scale: malloc", 0, NULL, NULL);
        return;
    }

    static const char *src_names[] = {
        "U.C. Berkeley", "MIT", "univ of technology",
        "King's College London", "Al-Azhar Univ",
        "KAIST", "EPFL", "LSE", "NUS", "UNSW",
        NULL
    };
    static const char *src_countries[] = {
        "usa","usa","uk","uk","egypt",
        "korea","switzerland","uk","sg","australia",
        NULL
    };

    /* Build CSV */
    FILE *fp = fopen(path, "w");
    if (!fp) {
        free(recs1); free(recs2);
        chk("idempotent_scale: create file", 0, NULL, NULL);
        return;
    }

    int n_src = 0;
    while (src_names[n_src]) n_src++;

    fprintf(fp, "University,Country,Rank Min,Rank Max,Overall Score\n");
    for (int i = 0; i < N; i++)
        fprintf(fp, "%s,%s,%d,%d,%.2f\n",
                src_names[i % n_src],
                src_countries[i % n_src],
                i + 1, i + 1, 60.0 + (i % 40));
    fclose(fp);

    /* First normalisation pass */
    int c1 = load_csv_data(path, recs1, N);
    for (int i = 0; i < c1; i++) normalize_record(&recs1[i]);

    /* Write normalised output, read back, normalise again */
    const char *path2 = "build/test_scale_idempotent2.csv";
    write_normalized_csv(path2, recs1, c1);
    int c2 = load_csv_data(path2, recs2, N);
    for (int i = 0; i < c2; i++) normalize_record(&recs2[i]);

    chk("idempotent_scale: both passes load same count",
        c1 == N && c2 == c1, NULL, NULL);

    int name_ok = 1, cty_ok = 1, rank_ok = 1;
    for (int i = 0; i < c1 && i < c2; i++) {
        if (strcmp(recs1[i].normalized_name,    recs2[i].normalized_name)    != 0) name_ok  = 0;
        if (strcmp(recs1[i].normalized_country, recs2[i].normalized_country) != 0) cty_ok   = 0;
        if (recs1[i].rank_min != recs2[i].rank_min ||
            recs1[i].rank_max != recs2[i].rank_max)                                rank_ok  = 0;
    }
    chk("idempotent_scale: 2000 names stable across two normalisation passes",
        name_ok, NULL, NULL);
    chk("idempotent_scale: 2000 countries stable across two passes",
        cty_ok, NULL, NULL);
    chk("idempotent_scale: 2000 ranks stable across two passes",
        rank_ok, NULL, NULL);

    remove(path);  remove(path2);
    free(recs1);   free(recs2);
}

/* ------------------------------------------------------------------ */
/*  10. Large-file write-then-read integrity                           */
/* ------------------------------------------------------------------ */

static void test_large_write_read(void)
{
    const int   N    = 50000;
    const char *path = "build/test_scale_large_rt.csv";

    UniversityRecord *recs_out;
    UniversityRecord *recs_in;

    recs_out = (UniversityRecord *)malloc((size_t)N * sizeof(UniversityRecord));
    recs_in  = (UniversityRecord *)malloc((size_t)N * sizeof(UniversityRecord));
    if (!recs_out || !recs_in) {
        free(recs_out); free(recs_in);
        chk("large_rt: malloc", 0, NULL, NULL);
        return;
    }

    /* Prepare N already-normalised records directly (bypass CSV generation) */
    static const char *names[] = {
        "MIT", "Stanford University", "University of Cambridge",
        "KAIST", "National University of Singapore",
        "University of Tokyo", "EPFL", "LSE", "UNSW", "CUHK"
    };
    static const char *ctys[] = {
        "United States","United States","United Kingdom",
        "South Korea","Singapore",
        "Japan","Switzerland","United Kingdom","Australia","Hong Kong SAR"
    };

    for (int i = 0; i < N; i++) {
        int idx = i % 10;
        memset(&recs_out[i], 0, sizeof(UniversityRecord));
        strncpy(recs_out[i].normalized_name,    names[idx], NAME_LEN    - 1);
        strncpy(recs_out[i].normalized_country, ctys[idx],  COUNTRY_LEN - 1);
        recs_out[i].rank_min = i + 1;
        recs_out[i].rank_max = i + 1;
        recs_out[i].score    = 60.0 + (double)(i % 40);
    }

    clock_t t0 = clock();
    int write_ok = write_normalized_csv(path, recs_out, N);
    int count    = load_csv_data(path, recs_in,  N);
    clock_t t1   = clock();
    double elapsed = (double)(t1 - t0) / CLOCKS_PER_SEC;

    printf("       large_rt: write+read %d records in %.3f s\n", N, elapsed);

    chk("large_rt: write succeeded",     write_ok == 1,  NULL, NULL);
    chk("large_rt: all 50 000 read back", count == N,    NULL, NULL);
    chk("large_rt: write+read < 5 s",    elapsed < 5.0, NULL, NULL);

    /* Spot-check: raw_name read back equals what was written */
    int name_ok = 1;
    for (int i = 0; i < count; i++) {
        if (strcmp(recs_in[i].raw_name,
                   recs_out[i].normalized_name) != 0) {
            name_ok = 0;
            break;
        }
    }
    chk("large_rt: all 50 000 names survive write→read verbatim",
        name_ok, NULL, NULL);

    remove(path);
    free(recs_out);
    free(recs_in);
}

/* ------------------------------------------------------------------ */
/*  main                                                               */
/* ------------------------------------------------------------------ */

int main(void)
{
    printf("==== PRODUCTION-SCALE STRESS TESTS ====\n\n");

    printf("--- 1.  100 000-record Throughput ---\n");
    test_100k_throughput();

    printf("\n--- 2.  Max-field-length Bulk (5 000 records) ---\n");
    test_max_field_bulk();

    printf("\n--- 3.  Dirty Bulk Data (10 000 rows, 10 %% malformed) ---\n");
    test_dirty_bulk();

    printf("\n--- 4.  CSV Round-trip at Scale (1 000 records) ---\n");
    test_round_trip_scale();

    printf("\n--- 5.  Normalization Consistency (500 × 15 inputs) ---\n");
    test_consistency();

    printf("\n--- 6.  All Rank Formats at Scale (10 000 records) ---\n");
    test_rank_format_scale();

    printf("\n--- 7.  All Country Aliases at Scale (10 000 records) ---\n");
    test_country_scale();

    printf("\n--- 8.  CSV Line-length Boundary ---\n");
    test_line_boundary();

    printf("\n--- 9.  Idempotency at Scale (2 000 records × 2 passes) ---\n");
    test_idempotency_scale();

    printf("\n--- 10. Large-file Write-then-Read Integrity (50 000 records) ---\n");
    test_large_write_read();

    printf("\n==== SCALE TEST SUMMARY ====\n");
    printf("Passed: %d / %d\n", g_pass, g_run);
    if (g_fail > 0) {
        printf("FAILED: %d test(s)\n", g_fail);
        return 1;
    }
    printf("All scale tests passed.\n");
    return 0;
}
