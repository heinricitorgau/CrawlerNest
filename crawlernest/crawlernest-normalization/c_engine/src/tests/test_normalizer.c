

#include <stdio.h>
#include <string.h>

#include "record.h"
#include "normalizer.h"

static int tests_run = 0;
static int tests_passed = 0;

static void print_test_result(const char *test_name, int passed) {
    tests_run++;

    if (passed) {
        tests_passed++;
        printf("[PASS] %s\n", test_name);
    } else {
        printf("[FAIL] %s\n", test_name);
    }
}

static void test_normalize_name_basic(void) {
    char output[NAME_LEN];

    normalize_name("U.C. Berkeley", output, NAME_LEN);
    print_test_result("normalize_name: U.C. Berkeley -> UC Berkeley",
                      strcmp(output, "UC Berkeley") == 0);
}

static void test_normalize_name_spaces(void) {
    char output[NAME_LEN];

    normalize_name("  University   of California, Berkeley  ", output, NAME_LEN);
    print_test_result("normalize_name: trim + collapse spaces",
                      strcmp(output, "University of California Berkeley") == 0);
}

static void test_normalize_name_acronym(void) {
    char output[NAME_LEN];

    normalize_name("massachusetts institute of technology MIT", output, NAME_LEN);
    print_test_result("normalize_name: MIT is preserved uppercase",
                      strcmp(output, "Massachusetts Institute of Technology MIT") == 0);
}

static void test_normalize_name_alias(void) {
    char output[NAME_LEN];

    normalize_name("California Institute of Technology (Caltech)", output, NAME_LEN);
    print_test_result("normalize_name: preserve parentheses (Caltech)",
                      strcmp(output, "California Institute of Technology (Caltech)") == 0);
}

static void test_normalize_country_usa(void) {
    char output[COUNTRY_LEN];

    normalize_country("U.S.A.", output, COUNTRY_LEN);
    print_test_result("normalize_country: U.S.A. -> United States",
                      strcmp(output, "United States") == 0);
}

static void test_normalize_country_taiwan(void) {
    char output[COUNTRY_LEN];

    normalize_country("ROC", output, COUNTRY_LEN);
    print_test_result("normalize_country: ROC -> Taiwan",
                      strcmp(output, "Taiwan") == 0);
}

static void test_parse_rank_single(void) {
    int rank_min = -1;
    int rank_max = -1;

    parse_rank("53", &rank_min, &rank_max);
    print_test_result("parse_rank: single rank",
                      rank_min == 53 && rank_max == 53);
}

static void test_parse_rank_range(void) {
    int rank_min = -1;
    int rank_max = -1;

    parse_rank("101-150", &rank_min, &rank_max);
    print_test_result("parse_rank: range rank",
                      rank_min == 101 && rank_max == 150);
}

static void test_parse_rank_top(void) {
    int rank_min = -1;
    int rank_max = -1;

    parse_rank("Top 100", &rank_min, &rank_max);
    print_test_result("parse_rank: Top 100",
                      rank_min == 1 && rank_max == 100);
}

static void test_parse_score_plain(void) {
    double score = parse_score("98.4");
    print_test_result("parse_score: plain score",
                      score > 98.39 && score < 98.41);
}

static void test_parse_score_with_label(void) {
    double score = parse_score("Score: 91.25");
    print_test_result("parse_score: labeled score",
                      score > 91.24 && score < 91.26);
}

static void test_normalize_record_pipeline(void) {
    UniversityRecord record;

    memset(&record, 0, sizeof(record));
    strcpy(record.raw_name, "U.C. Berkeley");
    strcpy(record.raw_country, "U.S.A.");
    strcpy(record.raw_rank, "Top 10");
    strcpy(record.raw_score, "Score: 98.4");

    normalize_record(&record);

    print_test_result("normalize_record: full pipeline",
                      strcmp(record.normalized_name, "UC Berkeley") == 0 &&
                      strcmp(record.normalized_country, "United States") == 0 &&
                      record.rank_min == 1 &&
                      record.rank_max == 10 &&
                      record.score > 98.39 && record.score < 98.41);
}

int main(void) {
    printf("==== Clawer C Data Normalization Engine Tests ====\n\n");

    test_normalize_name_basic();
    test_normalize_name_spaces();
    test_normalize_name_acronym();
    test_normalize_name_alias();
    test_normalize_country_usa();
    test_normalize_country_taiwan();
    test_parse_rank_single();
    test_parse_rank_range();
    test_parse_rank_top();
    test_parse_score_plain();
    test_parse_score_with_label();
    test_normalize_record_pipeline();

    printf("\n==== Test Summary ====\n");
    printf("Passed: %d / %d\n", tests_passed, tests_run);

    if (tests_passed == tests_run) {
        printf("All tests passed.\n");
        return 0;
    }

    printf("Some tests failed.\n");
    return 1;
}