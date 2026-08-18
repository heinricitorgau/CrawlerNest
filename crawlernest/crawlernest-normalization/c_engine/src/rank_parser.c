

#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/*
 * rank_parser.c
 *
 * Rank parsing helpers.
 *
 * Supported examples:
 * - "53"          -> rank_min = 53, rank_max = 53
 * - "Rank 53"     -> rank_min = 53, rank_max = 53
 * - "101-150"     -> rank_min = 101, rank_max = 150
 * - "201–250"     -> rank_min = 201, rank_max = 250  (en/em dash)
 * - "Top 100"     -> rank_min = 1,   rank_max = 100
 * - "=201"        -> rank_min = 201, rank_max = 201  (equal-sign prefix)
 * - "201+"        -> rank_min = 201, rank_max = 201  (open-ended floor)
 * - "#10"         -> rank_min = 10,  rank_max = 10   (hash prefix)
 *
 * 負數排名視為解析失敗，回傳 -1/-1。
 * If parsing fails, both values are set to -1.
 *
 * Fix I (Session 4): "Top"/"Rank" prefix matching is now case-insensitive.
 * Fix L (Session 4): integer overflow protection via strtol with range check.
 * Fix P (Session 5): "TOP 0" is now rejected (N must be >= 1).
 * Fix Q (Session 5): reversed range "B-A" (B > A) is auto-corrected to A-B.
 */

/*
 * MAX_REASONABLE_RANK
 *
 * Any parsed rank value larger than this is treated as a parsing failure.
 * Set to 9,999,999 to allow broad institutional datasets while still
 * catching overflow-derived garbage like strtol wrapping to a positive int.
 */
#define MAX_REASONABLE_RANK 9999999

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
 * safe_parse_int
 *
 * Parses an int from the string pointed to by *p, advancing *p past the
 * consumed characters.  Returns 1 on success (value written to *out), or 0
 * if the string is not a valid non-negative integer within MAX_REASONABLE_RANK.
 *
 * Fix L (Session 4): uses strtol so that very large values that would overflow
 * int are rejected rather than silently wrapping around.
 */
static int safe_parse_int(const char *s, int *out) {
    char *endptr;
    long val;

    if (s == NULL || out == NULL) {
        return 0;
    }

    errno = 0;
    val = strtol(s, &endptr, 10);

    if (endptr == s) {
        return 0;  /* no digits consumed */
    }

    if (errno == ERANGE || val < 0 || val > MAX_REASONABLE_RANK) {
        return 0;  /* out-of-range */
    }

    *out = (int)val;
    return 1;
}

/*
 * str_prefix_icase
 *
 * Fix I (Session 4): case-insensitive prefix match.
 * Returns a pointer to the character in `str` immediately after the prefix
 * `prefix`, or NULL if the prefix does not match (case-insensitively).
 */
static const char *str_prefix_icase(const char *str, const char *prefix) {
    while (*prefix != '\0') {
        if (tolower((unsigned char)*str) != tolower((unsigned char)*prefix)) {
            return NULL;
        }
        str++;
        prefix++;
    }
    return str;  /* points past the matched prefix */
}

/*
 * parse_rank
 *
 * Parses a raw rank string into rank_min and rank_max.
 */
void parse_rank(const char *input, int *rank_min, int *rank_max) {
    char temp[128];
    int a;

    if (rank_min == NULL || rank_max == NULL) {
        return;
    }

    *rank_min = -1;
    *rank_max = -1;

    if (input == NULL) {
        return;
    }

    normalize_dash_characters(input, temp, (int)sizeof(temp));

    {
        /* Skip leading whitespace for all cases */
        const char *p = temp;
        const char *after;
        int na, nb;

        while (*p != '\0' && (*p == ' ' || *p == '\t')) {
            p++;
        }

        /* Case 2 (Fix I): Top N — case-insensitive */
        after = str_prefix_icase(p, "top");
        if (after != NULL) {
            /* skip optional whitespace between "top" and the number */
            while (*after == ' ' || *after == '\t') { after++; }
            /*
             * Fix P (Session 5): reject "TOP 0" — a range of [1, 0] is
             * logically inconsistent (min > max).  Require N >= 1.
             */
            if (safe_parse_int(after, &a) && a >= 1) {
                *rank_min = 1;
                *rank_max = a;
                return;
            }
        }

        /* Case 3 (Fix I): Rank N — case-insensitive */
        after = str_prefix_icase(p, "rank");
        if (after != NULL) {
            while (*after == ' ' || *after == '\t') { after++; }
            if (safe_parse_int(after, &a)) {
                *rank_min = a;
                *rank_max = a;
                return;
            }
        }

        /* Case 4: =N — explicit-equal notation */
        if (*p == '=') {
            if (safe_parse_int(p + 1, &a)) {
                *rank_min = a;
                *rank_max = a;
                return;
            }
        }

        /* Case 5: #N — hash prefix notation (Fix C, Session 2) */
        if (*p == '#') {
            if (safe_parse_int(p + 1, &a)) {
                *rank_min = a;
                *rank_max = a;
                return;
            }
        }

        /* Case 1: range A-B (try before plain int to avoid A being consumed alone) */
        if (sscanf(p, "%d - %d", &na, &nb) == 2) {
            if (na < 0 || nb < 0 || na > MAX_REASONABLE_RANK || nb > MAX_REASONABLE_RANK) {
                return;
            }
            /*
             * Fix Q (Session 5): range reversal guard.
             * Inputs like "150-101" produce na=150, nb=101 (min > max).
             * Swap them so rank_min is always <= rank_max.
             */
            if (na > nb) {
                int tmp = na;
                na = nb;
                nb = tmp;
            }
            *rank_min = na;
            *rank_max = nb;
            return;
        }

        /* Case 6 (Fix L): plain integer via safe_parse_int */
        if (safe_parse_int(p, &a)) {
            *rank_min = a;
            *rank_max = a;
            return;
        }
    }
}
