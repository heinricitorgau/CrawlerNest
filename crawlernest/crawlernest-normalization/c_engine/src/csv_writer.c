

#include <stdio.h>

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

    fprintf(fp, "University,Country,Rank Min,Rank Max,Overall Score\n");

    for (i = 0; i < count; i++) {
        if (records[i].score < 0) {
            fprintf(fp, "%s,%s,%d,%d,\n",
                    records[i].normalized_name,
                    records[i].normalized_country,
                    records[i].rank_min,
                    records[i].rank_max);
        } else {
            fprintf(fp, "%s,%s,%d,%d,%.2f\n",
                    records[i].normalized_name,
                    records[i].normalized_country,
                    records[i].rank_min,
                    records[i].rank_max,
                    records[i].score);
        }
    }

    fclose(fp);
    return 1;
}