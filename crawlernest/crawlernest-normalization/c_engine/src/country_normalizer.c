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
    
    typedef struct {
        const char *alias;
        const char *canonical;
    } CountryMap;

    static const CountryMap mapping_table[] = {
        {"usa", "United States"},
        {"us", "United States"},
        {"u s a", "United States"},
        {"united states", "United States"},
        {"united states of america", "United States"},
        {"uk", "United Kingdom"},
        {"u k", "United Kingdom"},
        {"united kingdom", "United Kingdom"},
        {"great britain", "United Kingdom"},
        {"sg", "Singapore"},
        {"singapore", "Singapore"},
        {"china mainland", "China (Mainland)"},
        {"china", "China (Mainland)"},
        {"hong kong sar", "Hong Kong SAR"},
        {"hong kong", "Hong Kong SAR"},
        {"taiwan", "Taiwan"},
        {"republic of china", "Taiwan"},
        {"roc", "Taiwan"},
        {"south korea", "South Korea"},
        {"korea", "South Korea"},
        {"republic of korea", "South Korea"},
        {NULL, NULL}
    };

    if (input == NULL || output == NULL || size <= 0) {
        return;
    }

    normalize_basic(input, temp, (int)sizeof(temp));

    /* Search in mapping table */
    for (int i = 0; mapping_table[i].alias != NULL; i++) {
        if (strcmp(temp, mapping_table[i].alias) == 0) {
            safe_copy_string(output, (size_t)size, mapping_table[i].canonical);
            return;
        }
    }

    /* If not found in mapping table, use Title Case as fallback */
    safe_copy_string(output, (size_t)size, temp);
    to_title_case(output);
}