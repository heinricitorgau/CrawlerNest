#include <stdio.h>
#include <string.h>

#include "csv_writer.h"

/*
 * csv_writer.c
 *
 * First-version CSV export helper for normalized university data.
 *
 * This module writes normalized records to a CSV file so the pipeline becomes:
 * Raw CSV -> Load -> Normalize -> Export Clean CSV
 */

/*
 * needs_csv_quotes
 *
 * Returns 1 if a field must be quoted in CSV output.
 */
static int needs_csv_quotes(const char *field) {
    size_t i;

    if (field == NULL) {
        return 0;
    }

    for (i = 0; field[i] != '\0'; i++) {
        if (field[i] == ',' || field[i] == '"' || field[i] == '\n' || field[i] == '\r') {
            return 1;
        }
    }

    return 0;
}

/*
 * write_csv_field
 *
 * Writes a single CSV field, quoting and escaping it when needed.
 */
static int write_csv_field(FILE *fp, const char *field) {
    size_t i;

    if (fp == NULL) {
        return 0;
    }

    if (field == NULL) {
        field = "";
    }

    if (!needs_csv_quotes(field)) {
        return fprintf(fp, "%s", field) >= 0;
    }

    if (fputc('"', fp) == EOF) {
        return 0;
    }

    for (i = 0; field[i] != '\0'; i++) {
        if (field[i] == '"') {
            if (fputc('"', fp) == EOF || fputc('"', fp) == EOF) {
                return 0;
            }
        } else {
            if (fputc((unsigned char)field[i], fp) == EOF) {
                return 0;
            }
        }
    }

    return fputc('"', fp) != EOF;
}

/*
 * write_normalized_csv
 *
 * Writes normalized university records to a CSV file.
 *
 * Output format:
 * University,Country,Rank Min,Rank Max,Overall Score
 *
 * Returns:
 * - 1 on success
 * - 0 on failure
 */
int write_normalized_csv(const char *filename, const UniversityRecord records[], int count) {
    FILE *fp;
    int i;

    if (filename == NULL || records == NULL || count < 0) {
        fprintf(stderr, "Invalid arguments passed to write_normalized_csv().\n");
        return 0;
    }

    fp = fopen(filename, "w");
    if (fp == NULL) {
        perror("Failed to open output CSV file");
        return 0;
    }

    if (fprintf(fp, "University,Country,Rank Min,Rank Max,Overall Score\n") < 0) {
        fclose(fp);
        return 0;
    }

    for (i = 0; i < count; i++) {
        /*
         * Fix H (Session 3): when rank parsing failed (rank_min == -1),
         * write empty rank fields instead of "-1,-1" so the output CSV
         * contains only valid normalized data.  A warning is printed to
         * stderr so the caller knows a record was not fully resolved.
         */
        if (!write_csv_field(fp, records[i].normalized_name) ||
            fputc(',', fp) == EOF ||
            !write_csv_field(fp, records[i].normalized_country)) {
            fclose(fp);
            return 0;
        }

        if (records[i].rank_min < 0) {
            fprintf(stderr,
                    "csv_writer: record %d has unresolved rank; writing empty rank fields.\n",
                    i);
            if (fprintf(fp, ",,,") < 0) {
                fclose(fp);
                return 0;
            }
        } else {
            if (fprintf(fp, ",%d,%d,", records[i].rank_min, records[i].rank_max) < 0) {
                fclose(fp);
                return 0;
            }
        }

        if (records[i].score < 0) {
            if (fputc('\n', fp) == EOF) {
                fclose(fp);
                return 0;
            }
        } else {
            if (fprintf(fp, "%.2f\n", records[i].score) < 0) {
                fclose(fp);
                return 0;
            }
        }
    }

    if (fclose(fp) != 0) {
        return 0;
    }

    return 1;
}
