

#ifndef RECORD_H
#define RECORD_H

/*
 * record.h
 *
 * Data structure definitions used by the Clawer C Data Normalization Engine.
 *
 * This file defines the main record structure used to store both raw and
 * normalized university data fields.
 */

#include <stdio.h>

#define NAME_LEN 150
#define COUNTRY_LEN 80
#define RANK_STR_LEN 50
#define SCORE_STR_LEN 50

/*
 * UniversityRecord
 *
 * Stores a single university entry including both raw input data
 * and normalized output fields.
 */
typedef struct {

    /* Raw input fields */
    char raw_name[NAME_LEN];
    char raw_country[COUNTRY_LEN];
    char raw_rank[RANK_STR_LEN];
    char raw_score[SCORE_STR_LEN];

    /* Normalized fields */
    char normalized_name[NAME_LEN];
    char normalized_country[COUNTRY_LEN];

    int rank_min;
    int rank_max;

    double score;

} UniversityRecord;

#endif /* RECORD_H */