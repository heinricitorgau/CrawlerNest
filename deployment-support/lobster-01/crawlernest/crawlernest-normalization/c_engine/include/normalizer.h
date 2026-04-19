#ifndef NORMALIZER_H
#define NORMALIZER_H

/*
 * normalizer.h
 *
 * Function declarations for the Clawer C Data Normalization Engine.
 *
 * This header defines the core normalization interface used to transform
 * raw university data into standardized structured fields.
 */

#include "record.h"

/*
 * normalize_name
 *
 * Normalizes a university name string.
 *
 * Parameters:
 * - input:  raw university name
 * - output: destination buffer for normalized name
 * - size:   size of destination buffer
 */
void normalize_name(const char *input, char *output, int size);

/*
 * normalize_country
 *
 * Normalizes a country name string.
 *
 * Parameters:
 * - input:  raw country name
 * - output: destination buffer for normalized country name
 * - size:   size of destination buffer
 */
void normalize_country(const char *input, char *output, int size);

/*
 * parse_rank
 *
 * Parses a rank string into structured numeric range fields.
 *
 * Parameters:
 * - input:    raw rank string
 * - rank_min: output minimum rank
 * - rank_max: output maximum rank
 */
void parse_rank(const char *input, int *rank_min, int *rank_max);

/*
 * parse_score
 *
 * Parses a score string into a numeric value.
 *
 * Parameters:
 * - input: raw score string
 *
 * Returns:
 * - parsed score value
 */
double parse_score(const char *input);

/*
 * normalize_record
 *
 * Applies normalization to a single UniversityRecord.
 */
void normalize_record(UniversityRecord *record);

/*
 * normalize_dataset
 *
 * Applies normalization to all records in an array.
 *
 * Parameters:
 * - records: array of UniversityRecord
 * - count:   number of records to normalize
 */
void normalize_dataset(UniversityRecord records[], int count);

#endif /* NORMALIZER_H */
