#include <stddef.h>
#include <string.h>
#include <ctype.h>

#include "utils.h"

/*
 * name_normalizer.c
 *
 * Enhanced university name normalization helpers.
 *
 * Current capabilities:
 * - UTF-8 Latin Extended accent stripping (0xC3 and 0xC5 prefix sequences)
 * - trim leading/trailing spaces
 * - remove punctuation characters
 * - convert output to lowercase
 * - collapse repeated internal spaces
 * - remove stopwords: the, of, and, for, a, an
 * - expand common abbreviations: inst, tech, univ, natl, intl, coll, sci, engr
 */

/*
 * strip_accents_utf8
 *
 * Converts UTF-8 encoded Latin Extended accented characters to their ASCII
 * equivalents. Handles:
 *   - 0xC3 prefix sequences (U+00C0-U+00FF): é→e, è→e, ê→e, ë→e,
 *     à→a, â→a, ä→a, ô→o, ö→o, ü→u, ù→u, û→u, ï→i, î→i,
 *     ñ→n, ç→c, ß→ss, Ø/ø→o, å→a, æ/Æ→ae
 *   - 0xC5 prefix sequences: Ł/ł→l, Œ/œ→oe
 * All accented chars are output as lowercase ASCII.
 * Other multi-byte sequences are skipped.
 */
static void strip_accents_utf8(char *output, size_t out_size, const char *input) {
    size_t in_i  = 0;
    size_t out_i = 0;
    unsigned char b0, b1;

    if (input == NULL || output == NULL || out_size == 0) {
        return;
    }

    while (input[in_i] != '\0' && out_i + 1 < out_size) {
        b0 = (unsigned char)input[in_i];

        if (b0 < 0x80) {
            /* Plain ASCII — copy as-is */
            output[out_i++] = (char)b0;
            in_i++;
        } else if (b0 == 0xC3 && input[in_i + 1] != '\0') {
            b1 = (unsigned char)input[in_i + 1];
            in_i += 2;
            /*
             * Second byte 0x80–0xBF covers U+00C0–U+00FF.
             * Output lowercase ASCII replacement.
             */
            switch (b1) {
                /* À Á Â Ã Ä Å / à á â ã ä å  → a */
                case 0x80: case 0x81: case 0x82: case 0x83: case 0x84: case 0x85:
                case 0xA0: case 0xA1: case 0xA2: case 0xA3: case 0xA4: case 0xA5:
                    if (out_i + 1 < out_size) output[out_i++] = 'a';
                    break;

                /* Æ / æ  → ae */
                case 0x86: case 0xA6:
                    if (out_i + 2 < out_size) {
                        output[out_i++] = 'a';
                        output[out_i++] = 'e';
                    }
                    break;

                /* Ç / ç  → c */
                case 0x87: case 0xA7:
                    if (out_i + 1 < out_size) output[out_i++] = 'c';
                    break;

                /* È É Ê Ë / è é ê ë  → e */
                case 0x88: case 0x89: case 0x8A: case 0x8B:
                case 0xA8: case 0xA9: case 0xAA: case 0xAB:
                    if (out_i + 1 < out_size) output[out_i++] = 'e';
                    break;

                /* Ì Í Î Ï / ì í î ï  → i */
                case 0x8C: case 0x8D: case 0x8E: case 0x8F:
                case 0xAC: case 0xAD: case 0xAE: case 0xAF:
                    if (out_i + 1 < out_size) output[out_i++] = 'i';
                    break;

                /* Ñ / ñ  → n */
                case 0x91: case 0xB1:
                    if (out_i + 1 < out_size) output[out_i++] = 'n';
                    break;

                /* Ò Ó Ô Õ Ö / ò ó ô õ ö  → o */
                case 0x92: case 0x93: case 0x94: case 0x95: case 0x96:
                case 0xB2: case 0xB3: case 0xB4: case 0xB5: case 0xB6:
                    if (out_i + 1 < out_size) output[out_i++] = 'o';
                    break;

                /* Ø / ø  → o */
                case 0x98: case 0xB8:
                    if (out_i + 1 < out_size) output[out_i++] = 'o';
                    break;

                /* Ù Ú Û Ü / ù ú û ü  → u */
                case 0x99: case 0x9A: case 0x9B: case 0x9C:
                case 0xB9: case 0xBA: case 0xBB: case 0xBC:
                    if (out_i + 1 < out_size) output[out_i++] = 'u';
                    break;

                /* ß  → ss */
                case 0x9F:
                    if (out_i + 2 < out_size) {
                        output[out_i++] = 's';
                        output[out_i++] = 's';
                    }
                    break;

                /* Å / å  already covered in 'a' group above */
                default:
                    /* Unknown second byte — skip silently */
                    break;
            }
        } else if (b0 == 0xC5 && input[in_i + 1] != '\0') {
            b1 = (unsigned char)input[in_i + 1];
            in_i += 2;
            switch (b1) {
                /* Ł (0xC5 0x81) / ł (0xC5 0x82)  → l */
                case 0x81: case 0x82:
                    if (out_i + 1 < out_size) output[out_i++] = 'l';
                    break;

                /* Œ (0xC5 0x92) / œ (0xC5 0x93)  → oe */
                case 0x92: case 0x93:
                    if (out_i + 2 < out_size) {
                        output[out_i++] = 'o';
                        output[out_i++] = 'e';
                    }
                    break;

                default:
                    break;
            }
        } else {
            /* Other multi-byte lead byte — skip this and its continuation bytes */
            in_i++;
            while ((unsigned char)input[in_i] >= 0x80 &&
                   (unsigned char)input[in_i] <  0xC0) {
                in_i++;
            }
        }
    }

    output[out_i] = '\0';
}

/*
 * remove_stopwords
 *
 * Removes standalone stopword tokens from a whitespace-separated lowercase
 * string, modifying it in place.
 * Stopwords: "the", "of", "and", "for", "a", "an"
 */
static void remove_stopwords(char *str) {
    static const char *stopwords[] = {
        "the", "of", "and", "for", "a", "an", NULL
    };

    char  temp[512];
    char  result[512];
    char *tok;
    size_t result_len = 0;
    size_t tok_len;
    int   is_stop;
    int   i;

    if (str == NULL) {
        return;
    }

    strncpy(temp, str, sizeof(temp) - 1);
    temp[sizeof(temp) - 1] = '\0';
    result[0] = '\0';

    tok = strtok(temp, " ");
    while (tok != NULL) {
        is_stop = 0;
        for (i = 0; stopwords[i] != NULL; i++) {
            if (strcmp(tok, stopwords[i]) == 0) {
                is_stop = 1;
                break;
            }
        }

        if (!is_stop) {
            tok_len = strlen(tok);
            if (result_len > 0 && result_len + 1 < sizeof(result)) {
                result[result_len++] = ' ';
            }
            if (result_len + tok_len < sizeof(result)) {
                memcpy(result + result_len, tok, tok_len);
                result_len += tok_len;
            }
        }

        tok = strtok(NULL, " ");
    }

    result[result_len] = '\0';

    /* result is always <= str in length (only removing), safe to copy back */
    memcpy(str, result, result_len + 1);
}

/*
 * expand_abbreviations
 *
 * Expands common university name abbreviations in a whitespace-separated
 * lowercase string.
 *
 * Lookup table:
 *   inst  → institute
 *   tech  → technology
 *   univ  → university
 *   natl  → national
 *   intl  → international
 *   coll  → college
 *   sci   → science
 *   engr  → engineering
 */
static void expand_abbreviations(char *str, size_t str_size) {
    typedef struct {
        const char *abbrev;
        const char *expanded;
    } AbbrevEntry;

    static const AbbrevEntry abbrev_table[] = {
        {"inst",  "institute"},
        {"tech",  "technology"},
        {"univ",  "university"},
        {"natl",  "national"},
        {"intl",  "international"},
        {"coll",  "college"},
        {"sci",   "science"},
        {"engr",  "engineering"},
        {NULL,    NULL}
    };

    char  temp[512];
    char  result[512];
    char *tok;
    size_t result_len = 0;
    size_t tok_len;
    const char *replacement;
    int   i;

    if (str == NULL || str_size == 0) {
        return;
    }

    strncpy(temp, str, sizeof(temp) - 1);
    temp[sizeof(temp) - 1] = '\0';
    result[0] = '\0';

    tok = strtok(temp, " ");
    while (tok != NULL) {
        replacement = tok;

        for (i = 0; abbrev_table[i].abbrev != NULL; i++) {
            if (strcmp(tok, abbrev_table[i].abbrev) == 0) {
                replacement = abbrev_table[i].expanded;
                break;
            }
        }

        tok_len = strlen(replacement);
        if (result_len > 0 && result_len + 1 < sizeof(result)) {
            result[result_len++] = ' ';
        }
        if (result_len + tok_len < sizeof(result)) {
            memcpy(result + result_len, replacement, tok_len);
            result_len += tok_len;
        }

        tok = strtok(NULL, " ");
    }

    result[result_len] = '\0';

    strncpy(str, result, str_size - 1);
    str[str_size - 1] = '\0';
}

/*
 * normalize_name
 *
 * Normalizes a raw university name string into a simplified comparable form.
 *
 * Pipeline:
 * 1. strip_accents_utf8  — é→e, ü→u, ß→ss, æ→ae, Ł→l, œ→oe …
 * 2. trim_whitespace     — remove leading/trailing spaces
 * 3. remove_punctuation  — strip punctuation (except parentheses)
 * 4. to_lowercase        — lowercase entire string
 * 5. collapse_spaces     — collapse repeated spaces
 * 6. remove_stopwords    — drop: the, of, and, for, a, an
 * 7. expand_abbreviations — inst→institute, tech→technology, …
 * 8. trim_whitespace     — final cleanup
 */
void normalize_name(const char *input, char *output, int size) {
    char accent_buf[512];

    if (input == NULL || output == NULL || size <= 0) {
        return;
    }

    /* Step 1: Strip UTF-8 accent sequences to ASCII */
    strip_accents_utf8(accent_buf, sizeof(accent_buf), input);

    /* Step 2–5: Copy, trim, normalise punctuation, lowercase, collapse */
    safe_copy_string(output, (size_t)size, accent_buf);
    trim_whitespace(output);
    /* Replace hyphens and parentheses with spaces before punctuation removal */
    {
        size_t k;
        for (k = 0; output[k] != '\0'; k++) {
            if (output[k] == '-' || output[k] == '(' || output[k] == ')') {
                output[k] = ' ';
            }
        }
    }
    remove_punctuation(output);
    to_lowercase(output);
    collapse_spaces(output);

    /* Step 6: Remove stopwords */
    remove_stopwords(output);

    /* Step 7: Expand abbreviations */
    expand_abbreviations(output, (size_t)size);

    /* Step 8: Final trim */
    trim_whitespace(output);
}
