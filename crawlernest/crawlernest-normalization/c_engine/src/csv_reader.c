#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "csv_reader.h"
#include "utils.h"

#define CSV_LINE_LEN 1024
#define CSV_EXPECTED_COLUMNS 5
#define CSV_FIELD_LEN 256

typedef enum {
    CSV_PARSE_OK = 0,
    CSV_PARSE_TOO_MANY_FIELDS,
    CSV_PARSE_UNTERMINATED_QUOTE,
    CSV_PARSE_INVALID_QUOTE,
    CSV_PARSE_FIELD_TOO_LONG
} CsvParseStatus;

typedef struct {
    int idx_name;
    int idx_country;
    int idx_rank_min;
    int idx_rank_max;
    int idx_score;
} CsvHeaderMap;

/*
 * parse_csv_row
 *
 * Parses one CSV row into fixed-size field buffers.
 *
 * Supported:
 * - quoted fields
 * - commas inside quoted fields
 * - escaped quotes using ""
 *
 * This parser treats one input line as one CSV row.
 */
static CsvParseStatus parse_csv_row(
    const char *line,
    char fields[][CSV_FIELD_LEN],
    int max_fields,
    int *out_field_count
) {
    int field_index = 0;
    int char_index = 0;
    int in_quotes = 0;
    int after_closing_quote = 0;
    int i;

    if (line == NULL || fields == NULL || out_field_count == NULL || max_fields <= 0) {
        return CSV_PARSE_INVALID_QUOTE;
    }

    for (i = 0; i < max_fields; i++) {
        fields[i][0] = '\0';
    }

    for (i = 0; line[i] != '\0'; i++) {
        char ch = line[i];

        if (in_quotes) {
            if (ch == '"') {
                if (line[i + 1] == '"') {
                    if (char_index >= CSV_FIELD_LEN - 1) {
                        return CSV_PARSE_FIELD_TOO_LONG;
                    }
                    fields[field_index][char_index++] = '"';
                    i++;
                } else {
                    in_quotes = 0;
                    after_closing_quote = 1;
                }
            } else {
                if (char_index >= CSV_FIELD_LEN - 1) {
                    return CSV_PARSE_FIELD_TOO_LONG;
                }
                fields[field_index][char_index++] = ch;
            }
            continue;
        }

        if (after_closing_quote) {
            if (ch == ',') {
                fields[field_index][char_index] = '\0';
                field_index++;
                if (field_index >= max_fields) {
                    return CSV_PARSE_TOO_MANY_FIELDS;
                }
                char_index = 0;
                after_closing_quote = 0;
            } else if (isspace((unsigned char)ch)) {
                continue;
            } else {
                return CSV_PARSE_INVALID_QUOTE;
            }
            continue;
        }

        if (ch == ',') {
            fields[field_index][char_index] = '\0';
            field_index++;
            if (field_index >= max_fields) {
                return CSV_PARSE_TOO_MANY_FIELDS;
            }
            char_index = 0;
        } else if (ch == '"') {
            if (char_index != 0) {
                return CSV_PARSE_INVALID_QUOTE;
            }
            in_quotes = 1;
        } else {
            if (char_index >= CSV_FIELD_LEN - 1) {
                return CSV_PARSE_FIELD_TOO_LONG;
            }
            fields[field_index][char_index++] = ch;
        }
    }

    if (in_quotes) {
        return CSV_PARSE_UNTERMINATED_QUOTE;
    }

    fields[field_index][char_index] = '\0';
    *out_field_count = field_index + 1;
    return CSV_PARSE_OK;
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
 * strip_utf8_bom
 *
 * Removes a UTF-8 BOM from the beginning of a line when present.
 */
static void strip_utf8_bom(char *str) {
    if (str == NULL) {
        return;
    }

    if ((unsigned char)str[0] == 0xEF &&
        (unsigned char)str[1] == 0xBB &&
        (unsigned char)str[2] == 0xBF) {
        memmove(str, str + 3, strlen(str + 3) + 1);
    }
}

/*
 * normalize_header_name
 *
 * Simplifies a header string for exact schema comparison.
 */
static void normalize_header_name(char *header) {
    if (header == NULL) {
        return;
    }

    trim_whitespace(header);
    collapse_spaces(header);
    to_lowercase(header);
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
 * report_csv_error
 *
 * Prints a line-numbered CSV parsing error.
 */
static void report_csv_error(int line_number, CsvParseStatus status) {
    const char *message = "unknown CSV parsing error";

    switch (status) {
        case CSV_PARSE_TOO_MANY_FIELDS:
            message = "too many columns in row";
            break;
        case CSV_PARSE_UNTERMINATED_QUOTE:
            message = "unterminated quoted field";
            break;
        case CSV_PARSE_INVALID_QUOTE:
            message = "invalid quote placement in row";
            break;
        case CSV_PARSE_FIELD_TOO_LONG:
            message = "field exceeds maximum supported length";
            break;
        case CSV_PARSE_OK:
        default:
            break;
    }

    fprintf(stderr, "CSV warning at line %d: %s.\n", line_number, message);
}

/*
 * validate_and_map_header
 *
 * Validates the expected schema and stores column indices.
 *
 * Expected header:
 * University,Country,Rank Min,Rank Max,Overall Score
 */
static int validate_and_map_header(
    char fields[][CSV_FIELD_LEN],
    int field_count,
    CsvHeaderMap *header_map
) {
    char normalized[CSV_FIELD_LEN];

    if (fields == NULL || header_map == NULL) {
        return 0;
    }

    if (field_count != CSV_EXPECTED_COLUMNS) {
        fprintf(stderr,
                "Error: invalid CSV header column count. Expected %d columns, got %d.\n",
                CSV_EXPECTED_COLUMNS,
                field_count);
        return 0;
    }

    header_map->idx_name = -1;
    header_map->idx_country = -1;
    header_map->idx_rank_min = -1;
    header_map->idx_rank_max = -1;
    header_map->idx_score = -1;

    safe_copy_string(normalized, sizeof(normalized), fields[0]);
    normalize_header_name(normalized);
    if (strcmp(normalized, "university") != 0) {
        fprintf(stderr, "Error: expected header column 1 to be 'University'.\n");
        return 0;
    }
    header_map->idx_name = 0;

    safe_copy_string(normalized, sizeof(normalized), fields[1]);
    normalize_header_name(normalized);
    if (strcmp(normalized, "country") != 0) {
        fprintf(stderr, "Error: expected header column 2 to be 'Country'.\n");
        return 0;
    }
    header_map->idx_country = 1;

    safe_copy_string(normalized, sizeof(normalized), fields[2]);
    normalize_header_name(normalized);
    if (strcmp(normalized, "rank min") != 0) {
        fprintf(stderr, "Error: expected header column 3 to be 'Rank Min'.\n");
        return 0;
    }
    header_map->idx_rank_min = 2;

    safe_copy_string(normalized, sizeof(normalized), fields[3]);
    normalize_header_name(normalized);
    if (strcmp(normalized, "rank max") != 0) {
        fprintf(stderr, "Error: expected header column 4 to be 'Rank Max'.\n");
        return 0;
    }
    header_map->idx_rank_max = 3;

    safe_copy_string(normalized, sizeof(normalized), fields[4]);
    normalize_header_name(normalized);
    if (strcmp(normalized, "overall score") != 0) {
        fprintf(stderr, "Error: expected header column 5 to be 'Overall Score'.\n");
        return 0;
    }
    header_map->idx_score = 4;

    return 1;
}

/*
 * map_row_to_record
 *
 * Copies parsed CSV fields into a UniversityRecord.
 */
static int map_row_to_record(
    char fields[][CSV_FIELD_LEN],
    int field_count,
    const CsvHeaderMap *header_map,
    UniversityRecord *record
) {
    if (fields == NULL || header_map == NULL || record == NULL) {
        return 0;
    }

    if (field_count != CSV_EXPECTED_COLUMNS) {
        return 0;
    }

    initialize_record(record);

    safe_copy_string(record->raw_name, NAME_LEN, fields[header_map->idx_name]);
    safe_copy_string(record->raw_country, COUNTRY_LEN, fields[header_map->idx_country]);

    /*
     * Fix M (Session 5): smart rank field combination.
     *
     * Previous code always used "%s-%s" which produced "-150" when
     * rank_min was empty, causing the rank parser to fail on a clearly
     * valid rank_max-only value.
     *
     * New logic:
     * - both empty       → raw_rank = ""         → parse_rank returns -1/-1
     * - only rank_max    → raw_rank = rank_max    → parsed as single rank
     * - only rank_min    → raw_rank = rank_min    → parsed as single rank
     * - both present     → raw_rank = "min-max"   → parsed as range (unchanged)
     */
    {
        const char *rmin = fields[header_map->idx_rank_min];
        const char *rmax = fields[header_map->idx_rank_max];
        int rmin_empty = (rmin[0] == '\0');
        int rmax_empty = (rmax[0] == '\0');

        if (rmin_empty && rmax_empty) {
            record->raw_rank[0] = '\0';
        } else if (rmin_empty) {
            snprintf(record->raw_rank, RANK_STR_LEN, "%s", rmax);
        } else if (rmax_empty) {
            snprintf(record->raw_rank, RANK_STR_LEN, "%s", rmin);
        } else {
            snprintf(record->raw_rank, RANK_STR_LEN, "%s-%s", rmin, rmax);
        }
    }

    safe_copy_string(record->raw_score, SCORE_STR_LEN, fields[header_map->idx_score]);

    return 1;
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
    char fields[CSV_EXPECTED_COLUMNS][CSV_FIELD_LEN];
    int record_count = 0;
    int line_number = 0;
    int field_count;
    CsvParseStatus parse_status;
    CsvHeaderMap header_map;

    if (filename == NULL || records == NULL || max_records <= 0) {
        fprintf(stderr, "Invalid arguments passed to load_csv_data().\n");
        return 0;
    }

    fp = fopen(filename, "r");
    if (fp == NULL) {
        perror("Failed to open CSV file");
        return 0;
    }

    if (fgets(line, sizeof(line), fp) == NULL) {
        fprintf(stderr, "Error: CSV file is empty.\n");
        fclose(fp);
        return 0;
    }

    line_number = 1;
    trim_newline(line);
    strip_utf8_bom(line);
    parse_status = parse_csv_row(line, fields, CSV_EXPECTED_COLUMNS, &field_count);
    if (parse_status != CSV_PARSE_OK) {
        fprintf(stderr, "Error: failed to parse CSV header.\n");
        report_csv_error(line_number, parse_status);
        fclose(fp);
        return 0;
    }

    if (!validate_and_map_header(fields, field_count, &header_map)) {
        fclose(fp);
        return 0;
    }

    while (fgets(line, sizeof(line), fp) != NULL) {
        line_number++;

        /*
         * Detect fgets truncation.
         *
         * fgets reads at most sizeof(line)-1 = CSV_LINE_LEN-1 chars and
         * always appends '\0'.  A complete line ends with '\n' (or is the
         * final line in the file, which may lack a trailing newline).
         *
         * If the buffer is full AND the last char is not '\n' AND we are
         * not yet at EOF, the physical line is longer than our buffer.
         * Reading the rest of the line and parsing the truncated first
         * chunk would create a "zombie record" with corrupted fields.
         * Instead we drain the remainder and skip the entire line.
         */
        {
            size_t linelen = strlen(line);
            if (linelen == CSV_LINE_LEN - 1 &&
                line[CSV_LINE_LEN - 2] != '\n' &&
                !feof(fp)) {
                int ch;
                fprintf(stderr,
                        "CSV warning at line %d: line exceeds %d bytes, skipping.\n",
                        line_number, CSV_LINE_LEN - 1);
                while ((ch = fgetc(fp)) != EOF && ch != '\n') { /* drain */ }
                continue;
            }
        }

        trim_newline(line);

        if (line[0] == '\0') {
            continue;
        }

        if (record_count >= max_records) {
            fprintf(stderr, "Warning: maximum record limit reached (%d).\n", max_records);
            break;
        }

        parse_status = parse_csv_row(line, fields, CSV_EXPECTED_COLUMNS, &field_count);
        if (parse_status != CSV_PARSE_OK) {
            report_csv_error(line_number, parse_status);
            continue;
        }

        if (field_count != CSV_EXPECTED_COLUMNS) {
            fprintf(stderr,
                    "CSV warning at line %d: expected %d columns, got %d.\n",
                    line_number,
                    CSV_EXPECTED_COLUMNS,
                    field_count);
            continue;
        }

        if (!map_row_to_record(fields, field_count, &header_map, &records[record_count])) {
            fprintf(stderr, "CSV warning at line %d: failed to map row into record.\n", line_number);
            continue;
        }

        record_count++;
    }

    fclose(fp);
    return record_count;
}
