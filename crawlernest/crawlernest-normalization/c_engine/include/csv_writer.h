#ifndef CSV_WRITER_H
#define CSV_WRITER_H

#include "record.h"

/*
 * write_normalized_csv
 *
 * Writes normalized university records to a CSV file.
 *
 * Parameters:
 * - filename: path to output CSV file
 * - records: array of UniversityRecord
 * - count: number of records to write
 *
 * Returns:
 * - 1 on success
 * - 0 on failure
 */
int write_normalized_csv(const char *filename, const UniversityRecord records[], int count);

#endif /* CSV_WRITER_H */
