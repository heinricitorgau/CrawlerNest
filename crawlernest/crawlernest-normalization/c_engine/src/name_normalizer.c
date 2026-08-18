#include <ctype.h>
#include <stddef.h>
#include <string.h>

#include "utils.h"

#define NAME_WORK_LEN 512

/*
 * name_normalizer.c
 *
 * Practical university-name normalization for a university-level project.
 *
 * Goals:
 * - clean whitespace
 * - preserve meaningful aliases such as "(UCB)"
 * - expand a few safe abbreviations
 * - keep names readable
 * - avoid aggressive destructive normalization
 */
/*
 * normalize_name_punctuation
 *
 * Replaces punctuation that commonly acts as a separator with spaces.
 * Apostrophes, hyphens, and parentheses are preserved to avoid damaging
 * valid university names and aliases.
 */
static void normalize_name_punctuation(char *str) {
    size_t read_idx = 0;
    size_t write_idx = 0;

    if (str == NULL) {
        return;
    }

    while (str[read_idx] != '\0') {
        char ch = str[read_idx];

        if (ch == '.') {
            read_idx++;
            continue;
        }

        if (ch == ',' || ch == ';' || ch == ':') {
            str[write_idx++] = ' ';
        } else {
            str[write_idx++] = ch;
        }

        read_idx++;
    }

    str[write_idx] = '\0';
}

/*
 * equals_ignore_case
 *
 * Compares two ASCII strings case-insensitively.
 */
static int equals_ignore_case(const char *a, const char *b) {
    size_t i = 0;

    if (a == NULL || b == NULL) {
        return 0;
    }

    while (a[i] != '\0' && b[i] != '\0') {
        if (tolower((unsigned char)a[i]) != tolower((unsigned char)b[i])) {
            return 0;
        }
        i++;
    }

    return a[i] == '\0' && b[i] == '\0';
}

/*
 * map_abbreviation
 *
 * Expands a small set of safe university-name abbreviations.
 */
static const char *map_abbreviation(const char *word) {
    if (equals_ignore_case(word, "univ")) {
        return "University";
    }

    if (equals_ignore_case(word, "inst")) {
        return "Institute";
    }

    /*
     * Fix G (Session 3): "Tech" is NOT expanded to "Technology".
     * Many universities use "Tech" as part of their official proper name
     * (Georgia Tech, Texas Tech University, Virginia Tech, etc.).
     * Expanding it silently corrupts those names.
     * Deliberately removed: if (equals_ignore_case(word, "tech")) ...
     */

    return word;
}

/*
 * expand_common_abbreviations
 *
 * Expands selected abbreviations token by token.
 */
static void expand_common_abbreviations(const char *input, char *output, size_t size) {
    size_t read_idx = 0;
    size_t write_idx = 0;

    if (input == NULL || output == NULL || size == 0) {
        return;
    }

    output[0] = '\0';

    while (input[read_idx] != '\0') {
        char word[NAME_WORK_LEN];  /* large enough for any single token */
        size_t word_len = 0;
        const char *replacement;
        size_t replacement_len;

        while (input[read_idx] == ' ') {
            read_idx++;
        }

        if (input[read_idx] == '\0') {
            break;
        }

        while (input[read_idx] != '\0' &&
               input[read_idx] != ' ' &&
               word_len < sizeof(word) - 1) {
            word[word_len++] = input[read_idx++];
        }
        word[word_len] = '\0';

        replacement = map_abbreviation(word);
        replacement_len = strlen(replacement);

        if (write_idx > 0 && write_idx < size - 1) {
            output[write_idx++] = ' ';
        }

        for (size_t i = 0; i < replacement_len && write_idx < size - 1; i++) {
            output[write_idx++] = replacement[i];
        }
    }

    output[write_idx] = '\0';
}

/*
 * is_name_acronym
 *
 * Preserves common university acronyms in uppercase.
 *
 * Also handles parenthetical forms such as "(UCB)" by stripping the
 * surrounding parentheses before checking, so that the entire token
 * "(UCB)" is still recognised and kept in UPPER CASE.
 */
static int is_name_acronym(const char *word, size_t len) {
    static const char *acronyms[] = {
        /* Flagship / well-known */
        "MIT", "UCB", "UCLA", "UCSD", "UC", "NUS", "NTU", "NYU", "UCL", "EPFL",
        /* Extended list (synced with utils.c is_acronym) */
        "KAIST", "POSTECH", "LSE", "KTH", "ANU", "UNSW", "CUHK",
        "UBA", "UNAM",
        /* Fix K (Session 4): additional well-known university acronyms */
        "ETH", "UBC", "HKUST", "TUM", "TU", "CEU", "UMD", "UVA",
        "UNC", "UCD", "UWA", "UTS", "RMIT", "UST", "IIT", "IIM",
        "IISC", "UM", "UQ", "UGA", "UIC", "UFL", "USF", "UAB",
        "UTK", "UTA", "UTD",
        /* Fix T (Session 6): additional well-known university acronyms */
        "KAUST", "HKU",
        NULL
    };
    /* Strip one layer of parentheses so "(UCB)" is treated as "UCB" */
    size_t start = 0, end = len;
    char   upper[32];
    int    i;

    if (len == 0) {
        return 0;
    }

    if (word[0] == '(') {
        start = 1;
    }
    if (len > 0 && word[len - 1] == ')') {
        end = len - 1;
    }

    if (end <= start) {
        return 0;
    }

    {
        size_t inner_len = end - start;
        if (inner_len >= sizeof(upper)) {
            return 0;
        }
        for (i = 0; i < (int)inner_len; i++) {
            upper[i] = (char)toupper((unsigned char)word[start + (size_t)i]);
        }
        upper[inner_len] = '\0';
    }

    for (i = 0; acronyms[i] != NULL; i++) {
        if (strcmp(upper, acronyms[i]) == 0) {
            return 1;
        }
    }

    return 0;
}

/*
 * is_lowercase_connector
 *
 * Returns 1 for short connector words that usually remain lowercase.
 */
static int is_lowercase_connector(const char *word, size_t len, int is_first_word) {
    if (is_first_word) {
        return 0;
    }

    if (len == 2 && equals_ignore_case(word, "of")) {
        return 1;
    }

    if (len == 3 && equals_ignore_case(word, "and")) {
        return 1;
    }

    if (len == 3 && equals_ignore_case(word, "the")) {
        return 1;
    }

    if (len == 3 && equals_ignore_case(word, "for")) {
        return 1;
    }

    /* 常見前置詞與介系詞——不在句首時保持小寫 */
    if (len == 2 && equals_ignore_case(word, "in")) {
        return 1;
    }

    if (len == 2 && equals_ignore_case(word, "at")) {
        return 1;
    }

    if (len == 2 && equals_ignore_case(word, "to")) {
        return 1;
    }

    if (len == 2 && equals_ignore_case(word, "by")) {
        return 1;
    }

    if (len == 1 && equals_ignore_case(word, "a")) {
        return 1;
    }

    if (len == 2 && equals_ignore_case(word, "an")) {
        return 1;
    }

    return 0;
}

/*
 * apply_readable_name_case
 *
 * Applies readable title casing while preserving common acronyms.
 * Hyphenated segments are capitalized separately.
 */
static void apply_readable_name_case(char *str) {
    char result[NAME_WORK_LEN];
    size_t read_idx = 0;
    size_t write_idx = 0;
    int word_index = 0;

    if (str == NULL) {
        return;
    }

    result[0] = '\0';

    while (str[read_idx] != '\0' && write_idx < sizeof(result) - 1) {
        if (str[read_idx] == ' ') {
            result[write_idx++] = ' ';
            read_idx++;
            continue;
        }

        {
            char word[NAME_WORK_LEN];  /* large enough for any single token */
            size_t word_len = 0;
            size_t i;

            while (str[read_idx] != '\0' &&
                   str[read_idx] != ' ' &&
                   word_len < sizeof(word) - 1) {
                word[word_len++] = str[read_idx++];
            }
            word[word_len] = '\0';

            if (is_name_acronym(word, word_len)) {
                for (i = 0; i < word_len && write_idx < sizeof(result) - 1; i++) {
                    result[write_idx++] = (char)toupper((unsigned char)word[i]);
                }
            } else if (is_lowercase_connector(word, word_len, word_index == 0)) {
                for (i = 0; i < word_len && write_idx < sizeof(result) - 1; i++) {
                    result[write_idx++] = (char)tolower((unsigned char)word[i]);
                }
            } else {
                int capitalize_next = 1;

                for (i = 0; i < word_len && write_idx < sizeof(result) - 1; i++) {
                    unsigned char ch = (unsigned char)word[i];

                    if (isalpha(ch)) {
                        if (capitalize_next) {
                            result[write_idx++] = (char)toupper(ch);
                            capitalize_next = 0;
                        } else {
                            result[write_idx++] = (char)tolower(ch);
                        }
                    } else {
                        result[write_idx++] = (char)ch;
                        capitalize_next = (ch == '-' || ch == '(' || ch == '/');
                    }
                }
            }

            word_index++;
        }
    }

    result[write_idx] = '\0';
    safe_copy_string(str, NAME_WORK_LEN, result);
}

/*
 * normalize_name
 *
 * Normalizes a raw university name into a readable canonical form.
 *
 * Strategy:
 * - trim whitespace
 * - normalize punctuation separators
 * - collapse spaces
 * - expand a few safe abbreviations
 * - apply readable casing
 */
void normalize_name(const char *input, char *output, int size) {
    char working[NAME_WORK_LEN];
    char expanded[NAME_WORK_LEN];

    if (input == NULL || output == NULL || size <= 0) {
        return;
    }

    safe_copy_string(working, sizeof(working), input);
    trim_whitespace(working);
    normalize_name_punctuation(working);
    collapse_spaces(working);
    trim_whitespace(working);

    expand_common_abbreviations(working, expanded, sizeof(expanded));
    collapse_spaces(expanded);
    trim_whitespace(expanded);
    apply_readable_name_case(expanded);

    safe_copy_string(output, (size_t)size, expanded);
}
