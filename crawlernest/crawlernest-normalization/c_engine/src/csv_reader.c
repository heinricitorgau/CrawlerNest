#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "csv_reader.h"
#include "utils.h"

#define CSV_LINE_LEN 512
#define MAX_FIELDS 11

/*
 * split_csv_line
 *
 * Splits a simple comma-separated line into fields.
 * This implementation is intended for controlled sample data and does not
 * fully support quoted commas.
 */
static int split_csv_line(char *line, char *fields[], int max_fields) {
    int count = 0;
    char *token = strtok(line, ",");

    while (token != NULL && count < max_fields) {
        fields[count++] = token;
        token = strtok(NULL, ",");
    }

    return count;
}

/*
 * trim_newline
 *
 * Removes trailing '\n' or '\r' characters from a string.
 */
static void trim_newline(char *str) {
    size_t len;

    if (str == NULL) {
        return;
    }

    len = strlen(str);
    while (len > 0 && (str[len - 1] == '\n' || str[len - 1] == '\r')) {
        str[len - 1] = '\0';
        len--;
    }
}

/*
 * initialize_record
 *
 * Initializes a UniversityRecord with default values.
 */
static void initialize_record(UniversityRecord *record) {
    if (record == NULL) {
        return;
    }

    record->raw_name[0] = '\0';
    record->raw_country[0] = '\0';
    record->raw_rank[0] = '\0';
    record->raw_score[0] = '\0';

    record->normalized_name[0] = '\0';
    record->normalized_country[0] = '\0';

    record->rank_min = -1;
    record->rank_max = -1;
    record->score = -1.0;
}

/*
 * load_csv_data
 *
 * Reads university data from a CSV file.
 * Handles dynamic header mapping for "University", "Country", "Rank", and "Score".
 *
 * Returns the number of successfully loaded records.
 */
int load_csv_data(const char *filename, UniversityRecord records[], int max_records) {
    FILE *fp;
    char line[CSV_LINE_LEN];
    int record_count = 0;
    int is_header = 1;

    int idx_name = -1;
    int idx_country = -1;
    int idx_rank_min = -1;
    int idx_rank_max = -1;
    int idx_score = -1;
    int idx_rank_legacy = -1;

    if (filename == NULL || records == NULL || max_records <= 0) {
        fprintf(stderr, "Invalid arguments passed to load_csv_data().\n");
        return 0;
    }

    fp = fopen(filename, "r");
    if (fp == NULL) {
        perror("Failed to open CSV file");
        return 0;
    }

    while (fgets(line, sizeof(line), fp) != NULL) {
        char *fields[MAX_FIELDS];
        int field_count;
        char temp_line[CSV_LINE_LEN];

        trim_newline(line);
        if (line[0] == '\0') {
            continue;
        }

        strncpy(temp_line, line, sizeof(temp_line) - 1);
        temp_line[sizeof(temp_line) - 1] = '\0';
        field_count = split_csv_line(temp_line, fields, MAX_FIELDS);

        if (is_header) {
            /* Detect field indices from header */
            for (int i = 0; i < field_count; i++) {
                char header[64];
                safe_copy_string(header, sizeof(header), fields[i]);
                trim_whitespace(header);
                to_lowercase(header);

                if (strstr(header, "university") || strstr(header, "name")) idx_name = i;
                else if (strstr(header, "country") || strstr(header, "region")) idx_country = i;
                else if (strstr(header, "rank min")) idx_rank_min = i;
                else if (strstr(header, "rank max")) idx_rank_max = i;
                else if (strstr(header, "rank")) idx_rank_legacy = i;
                else if (strstr(header, "score")) idx_score = i;
            }
            is_header = 0;
            continue;
        }

        if (record_count >= max_records) {
            fprintf(stderr, "Warning: maximum record limit reached (%d).\n", max_records);
            break;
        }

        /* Mandatory fields check */
        if (idx_name == -1 || idx_country == -1) {
            fprintf(stderr, "Error: Required columns (University, Country) not found in CSV header.\n");
            break;
        }

        initialize_record(&records[record_count]);

        /* Map University Name */
        if (idx_name < field_count) {
            safe_copy_string(records[record_count].raw_name, NAME_LEN, fields[idx_name]);
        }

        /* Map Country */
        if (idx_country < field_count) {
            safe_copy_string(records[record_count].raw_country, COUNTRY_LEN, fields[idx_country]);
        }

        /* Map Rank */
        if (idx_rank_min != -1 && idx_rank_max != -1 && idx_rank_min < field_count && idx_rank_max < field_count) {
            /* If we have discrete Min/Max columns, combine them for the parser or set directly */
            snprintf(records[record_count].raw_rank, RANK_STR_LEN, "%s-%s", fields[idx_rank_min], fields[idx_rank_max]);
        } else if (idx_rank_legacy != -1 && idx_rank_legacy < field_count) {
            safe_copy_string(records[record_count].raw_rank, RANK_STR_LEN, fields[idx_rank_legacy]);
        }

        /* Map Score */
        if (idx_score != -1 && idx_score < field_count) {
            safe_copy_string(records[record_count].raw_score, SCORE_STR_LEN, fields[idx_score]);
        }

        record_count++;
    }

    fclose(fp);
    return record_count;
}