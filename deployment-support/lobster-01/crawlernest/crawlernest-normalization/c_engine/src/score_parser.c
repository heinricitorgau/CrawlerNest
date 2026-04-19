#include <ctype.h>
#include <stdio.h>
#include <string.h>

/*
 * score_parser.c
 *
 * First-version score parsing helpers.
 *
 * Supported examples:
 * - "98.4"         -> 98.4
 * - " 98.40 "      -> 98.4
 * - "Score: 98.4"  -> 98.4
 * - "score 91.25"  -> 91.25
 *
 * If parsing fails, returns -1.0.
 */

/*
 * extract_first_number
 *
 * Scans a string and extracts the first numeric substring that looks like
 * an integer or floating-point number.
 *
 * Returns 1 on success, 0 on failure.
 */
static int extract_first_number(const char *input, char *number_buf, int size) {
    int i = 0;
    int j = 0;
    int started = 0;
    int dot_seen = 0;

    if (input == NULL || number_buf == NULL || size <= 1) {
        return 0;
    }

    while (input[i] != '\0') {
        unsigned char ch = (unsigned char)input[i];

        if (!started) {
            if (isdigit(ch) || ch == '-' || ch == '+') {
                started = 1;
                number_buf[j++] = (char)ch;
            }
        } else {
            if (isdigit(ch)) {
                if (j < size - 1) {
                    number_buf[j++] = (char)ch;
                }
            } else if (ch == '.' && !dot_seen) {
                dot_seen = 1;
                if (j < size - 1) {
                    number_buf[j++] = (char)ch;
                }
            } else {
                break;
            }
        }

        i++;
    }

    number_buf[j] = '\0';

    if (!started) {
        return 0;
    }

    if ((j == 1) && (number_buf[0] == '-' || number_buf[0] == '+')) {
        return 0;
    }

    return 1;
}

/*
 * parse_score
 *
 * Parses a raw score string into a double value.
 *
 * Returns:
 * - parsed floating-point score
 * - -1.0 if parsing fails
 */
double parse_score(const char *input) {
    char number_buf[64];
    double value;

    if (input == NULL) {
        return -1.0;
    }

    if (!extract_first_number(input, number_buf, (int)sizeof(number_buf))) {
        return -1.0;
    }

    if (sscanf(number_buf, "%lf", &value) == 1) {
        return value;
    }

    return -1.0;
}
