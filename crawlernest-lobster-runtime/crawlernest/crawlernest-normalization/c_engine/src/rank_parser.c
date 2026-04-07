

#include <ctype.h>
#include <stdio.h>
#include <string.h>

/*
 * rank_parser.c
 *
 * First-version rank parsing helpers.
 *
 * Supported examples:
 * - "53"          -> rank_min = 53, rank_max = 53
 * - "Rank 53"     -> rank_min = 53, rank_max = 53
 * - "101-150"     -> rank_min = 101, rank_max = 150
 * - "201–250"     -> rank_min = 201, rank_max = 250
 * - "Top 100"     -> rank_min = 1,   rank_max = 100
 *
 * If parsing fails, both values are set to -1.
 */

/*
 * normalize_dash_characters
 *
 * Replaces common non-ASCII dash characters with a normal hyphen so the input
 * becomes easier to parse.
 */
static void normalize_dash_characters(const char *input, char *output, int size) {
    int i = 0;
    int j = 0;

    if (input == NULL || output == NULL || size <= 0) {
        return;
    }

    while (input[i] != '\0' && j < size - 1) {
        unsigned char ch = (unsigned char)input[i];

        /*
         * Handle common UTF-8 en dash / em dash bytes conservatively by
         * skipping the multibyte sequence and inserting '-'.
         * This is a lightweight prototype approach.
         */
        if ((unsigned char)input[i] == 0xE2 &&
            (unsigned char)input[i + 1] == 0x80 &&
            ((unsigned char)input[i + 2] == 0x93 ||
             (unsigned char)input[i + 2] == 0x94)) {
            output[j++] = '-';
            i += 3;
            continue;
        }

        output[j++] = (char)ch;
        i++;
    }

    output[j] = '\0';
}

/*
 * parse_rank
 *
 * Parses a raw rank string into rank_min and rank_max.
 */
void parse_rank(const char *input, int *rank_min, int *rank_max) {
    char temp[128];
    int a, b;

    if (rank_min == NULL || rank_max == NULL) {
        return;
    }

    *rank_min = -1;
    *rank_max = -1;

    if (input == NULL) {
        return;
    }

    normalize_dash_characters(input, temp, (int)sizeof(temp));

    /* Case 1: range such as 101-150 */
    if (sscanf(temp, " %d - %d", &a, &b) == 2) {
        *rank_min = a;
        *rank_max = b;
        return;
    }

    /* Case 2: Top 100 */
    if (sscanf(temp, " Top %d", &a) == 1 ||
        sscanf(temp, " top %d", &a) == 1) {
        *rank_min = 1;
        *rank_max = a;
        return;
    }

    /* Case 3: Rank 53 */
    if (sscanf(temp, " Rank %d", &a) == 1 ||
        sscanf(temp, " rank %d", &a) == 1) {
        *rank_min = a;
        *rank_max = a;
        return;
    }

    /* Case 4: plain integer */
    if (sscanf(temp, " %d", &a) == 1) {
        *rank_min = a;
        *rank_max = a;
        return;
    }
}