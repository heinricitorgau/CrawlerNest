#include <stddef.h>

#include "normalizer.h"

/*
 * normalize_record
 *
 * Applies the normalization pipeline to a single record.
 *
 * The actual implementations of the helper functions are expected to be
 * provided by their corresponding modules:
 * - normalize_name      -> name_normalizer.c
 * - normalize_country   -> country_normalizer.c
 * - parse_rank          -> rank_parser.c
 * - parse_score         -> score_parser.c
 */
void normalize_record(UniversityRecord *record) {
    if (record == NULL) {
        return;
    }

    normalize_name(record->raw_name, record->normalized_name, NAME_LEN);
    normalize_country(record->raw_country, record->normalized_country, COUNTRY_LEN);
    parse_rank(record->raw_rank, &record->rank_min, &record->rank_max);
    record->score = parse_score(record->raw_score);
}

/*
 * normalize_dataset
 *
 * Applies normalization to all records in the dataset.
 */
void normalize_dataset(UniversityRecord records[], int count) {
    int i;

    if (records == NULL || count <= 0) {
        return;
    }

    for (i = 0; i < count; i++) {
        normalize_record(&records[i]);
    }
}