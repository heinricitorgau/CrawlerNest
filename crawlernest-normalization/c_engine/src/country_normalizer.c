#include <stddef.h>
#include <string.h>

#include "utils.h"

/*
 * country_normalizer.c
 *
 * First-version country normalization helpers.
 *
 * Current capabilities:
 * - trim leading/trailing spaces
 * - collapse repeated internal spaces
 * - remove punctuation characters
 * - convert output to lowercase
 * - map common aliases to canonical names
 *
 * This file now reuses common string utilities from utils.c
 * to reduce duplicated logic across normalization modules.
 */

/*
 * normalize_basic
 *
 * Converts the input string into a simplified comparable form.
 */
static void normalize_basic(const char *input, char *output, int size) {
    if (input == NULL || output == NULL || size <= 0) {
        return;
    }

    safe_copy_string(output, (size_t)size, input);
    trim_whitespace(output);
    remove_punctuation(output);
    to_lowercase(output);
    collapse_spaces(output);
    trim_whitespace(output);
}

/*
 * normalize_country
 *
 * Normalizes a raw country string into a canonical country name.
 *
 * Current alias mappings include common variants such as:
 * - usa / us / u s a        -> United States
 * - uk / u k                -> United Kingdom
 */
void normalize_country(const char *input, char *output, int size) {
    char temp[128];

    if (input == NULL || output == NULL || size <= 0) {
        return;
    }

    normalize_basic(input, temp, (int)sizeof(temp));

    if (strcmp(temp, "usa") == 0 ||
        strcmp(temp, "us") == 0 ||
        strcmp(temp, "u s a") == 0 ||
        strcmp(temp, "united states") == 0 ||
        strcmp(temp, "united states of america") == 0) {
        safe_copy_string(output, (size_t)size, "United States");
    } else if (strcmp(temp, "uk") == 0 ||
               strcmp(temp, "u k") == 0 ||
               strcmp(temp, "united kingdom") == 0 ||
               strcmp(temp, "great britain") == 0) {
        safe_copy_string(output, (size_t)size, "United Kingdom");
    } else if (strcmp(temp, "taiwan") == 0 ||
               strcmp(temp, "republic of china") == 0 ||
               strcmp(temp, "roc") == 0) {
        safe_copy_string(output, (size_t)size, "Taiwan");
    } else if (strcmp(temp, "south korea") == 0 ||
               strcmp(temp, "korea") == 0 ||
               strcmp(temp, "republic of korea") == 0) {
        safe_copy_string(output, (size_t)size, "South Korea");
    } else {
        /* Default behavior: keep the normalized basic form. */
        safe_copy_string(output, (size_t)size, temp);
    }
}