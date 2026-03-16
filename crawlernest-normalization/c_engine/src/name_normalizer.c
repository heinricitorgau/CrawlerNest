#include <stddef.h>

#include "utils.h"

/*
 * name_normalizer.c
 *
 * First-version university name normalization helpers.
 *
 * Current capabilities:
 * - trim leading/trailing spaces
 * - collapse repeated internal spaces
 * - remove punctuation characters
 * - convert output to lowercase
 *
 * This file now reuses common string utilities from utils.c
 * to reduce duplicated logic across normalization modules.
 */

/*
 * normalize_name
 *
 * Normalizes a raw university name string into a simplified comparable form.
 *
 * Rules:
 * - copy input safely into output
 * - remove leading/trailing spaces
 * - remove punctuation
 * - convert uppercase to lowercase
 * - collapse multiple spaces into one
 */
void normalize_name(const char *input, char *output, int size) {
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