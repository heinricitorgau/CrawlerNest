#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include "csv_reader.h"
#include "csv_writer.h"
#include "record.h"
#include "normalizer.h"

static int tests_run = 0;
static int tests_passed = 0;

#define TEST_FILE_BUFFER_SIZE 4096

static int write_text_file(const char *filename, const char *content) {
    FILE *fp = fopen(filename, "w");

    if (fp == NULL) {
        return 0;
    }

    if (fputs(content, fp) == EOF) {
        fclose(fp);
        return 0;
    }

    return fclose(fp) == 0;
}

static int read_text_file(const char *filename, char *buffer, size_t buffer_size) {
    FILE *fp;
    size_t bytes_read;

    if (filename == NULL || buffer == NULL || buffer_size == 0) {
        return 0;
    }

    fp = fopen(filename, "r");
    if (fp == NULL) {
        return 0;
    }

    bytes_read = fread(buffer, 1, buffer_size - 1, fp);
    buffer[bytes_read] = '\0';

    if (ferror(fp)) {
        fclose(fp);
        return 0;
    }

    return fclose(fp) == 0;
}

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

static void test_csv_writer_escapes_comma_and_quotes(void) {
    const char *filename = "build/test_writer_escape.csv";
    char output[TEST_FILE_BUFFER_SIZE];
    UniversityRecord record;

    memset(&record, 0, sizeof(record));
    strcpy(record.normalized_name, "King's College, London");
    strcpy(record.normalized_country, "He said \"UK\"");
    record.rank_min = 35;
    record.rank_max = 35;
    record.score = 91.5;

    if (!write_normalized_csv(filename, &record, 1) ||
        !read_text_file(filename, output, sizeof(output))) {
        print_test_result("csv_writer: escape comma and quotes", 0);
        remove(filename);
        return;
    }

    print_test_result("csv_writer: escape comma and quotes",
                      strstr(output, "\"King's College, London\",\"He said \"\"UK\"\"\",35,35,91.50\n") != NULL);
    remove(filename);
}

static void test_csv_writer_quotes_newline_field(void) {
    const char *filename = "build/test_writer_newline.csv";
    char output[TEST_FILE_BUFFER_SIZE];
    UniversityRecord record;

    memset(&record, 0, sizeof(record));
    strcpy(record.normalized_name, "Line One\nLine Two");
    strcpy(record.normalized_country, "Singapore");
    record.rank_min = 8;
    record.rank_max = 8;
    record.score = 95.0;

    if (!write_normalized_csv(filename, &record, 1) ||
        !read_text_file(filename, output, sizeof(output))) {
        print_test_result("csv_writer: quote newline field", 0);
        remove(filename);
        return;
    }

    print_test_result("csv_writer: quote newline field",
                      strstr(output, "\"Line One\nLine Two\",Singapore,8,8,95.00\n") != NULL);
    remove(filename);
}

static void test_csv_reader_rejects_malformed_header(void) {
    const char *filename = "build/test_bad_header.csv";
    UniversityRecord records[4];
    int count;
    const char *csv_content =
        "University,Country,Rank,Score\n"
        "MIT,United States,1,98.4\n";

    if (!write_text_file(filename, csv_content)) {
        print_test_result("csv_reader: malformed header", 0);
        remove(filename);
        return;
    }

    count = load_csv_data(filename, records, 4);
    print_test_result("csv_reader: malformed header", count == 0);
    remove(filename);
}

static void test_csv_reader_skips_malformed_row(void) {
    const char *filename = "build/test_bad_row.csv";
    UniversityRecord records[4];
    int count;
    const char *csv_content =
        "University,Country,Rank Min,Rank Max,Overall Score\n"
        "\"Bad Row,United States,1,1,99.0\n"
        "MIT,United States,1,1,98.4\n";

    if (!write_text_file(filename, csv_content)) {
        print_test_result("csv_reader: malformed row skipped", 0);
        remove(filename);
        return;
    }

    count = load_csv_data(filename, records, 4);
    print_test_result("csv_reader: malformed row skipped",
                      count == 1 &&
                      strcmp(records[0].raw_name, "MIT") == 0 &&
                      strcmp(records[0].raw_country, "United States") == 0);
    remove(filename);
}

static void test_csv_round_trip_with_escaped_fields(void) {
    const char *filename = "build/test_round_trip.csv";
    UniversityRecord output_record;
    UniversityRecord loaded_records[2];
    int count;

    memset(&output_record, 0, sizeof(output_record));
    strcpy(output_record.normalized_name, "College, of \"Engineering\"");
    strcpy(output_record.normalized_country, "Bosnia, \"Region\"");
    output_record.rank_min = 12;
    output_record.rank_max = 20;
    output_record.score = 88.75;

    if (!write_normalized_csv(filename, &output_record, 1)) {
        print_test_result("csv round trip: escaped fields", 0);
        remove(filename);
        return;
    }

    count = load_csv_data(filename, loaded_records, 2);
    print_test_result("csv round trip: escaped fields",
                      count == 1 &&
                      strcmp(loaded_records[0].raw_name, "College, of \"Engineering\"") == 0 &&
                      strcmp(loaded_records[0].raw_country, "Bosnia, \"Region\"") == 0 &&
                      strcmp(loaded_records[0].raw_rank, "12-20") == 0);
    remove(filename);
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
    test_csv_writer_escapes_comma_and_quotes();
    test_csv_writer_quotes_newline_field();
    test_csv_reader_rejects_malformed_header();
    test_csv_reader_skips_malformed_row();
    test_csv_round_trip_with_escaped_fields();

    printf("\n==== Test Summary ====\n");
    printf("Passed: %d / %d\n", tests_passed, tests_run);

    if (tests_passed == tests_run) {
        printf("All tests passed.\n");
        return 0;
    }

    printf("Some tests failed.\n");
    return 1;
}
