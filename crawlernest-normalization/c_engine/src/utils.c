#include <ctype.h>
#include <stddef.h>
#include <string.h>

#include "utils.h"

/*
 * trim_whitespace
 *
 * Removes leading and trailing whitespace from a string in place.
 */
void trim_whitespace(char *str) {
    char *start;
    char *end;
    size_t len;

    if (str == NULL || str[0] == '\0') {
        return;
    }

    start = str;
    while (*start != '\0' && isspace((unsigned char)*start)) {
        start++;
    }

    if (*start == '\0') {
        str[0] = '\0';
        return;
    }

    end = start + strlen(start) - 1;
    while (end > start && isspace((unsigned char)*end)) {
        end--;
    }
    *(end + 1) = '\0';

    if (start != str) {
        len = strlen(start);
        memmove(str, start, len + 1);
    }
}

/*
 * to_lowercase
 *
 * Converts a string to lowercase in place.
 */
void to_lowercase(char *str) {
    size_t i;

    if (str == NULL) {
        return;
    }

    for (i = 0; str[i] != '\0'; i++) {
        str[i] = (char)tolower((unsigned char)str[i]);
    }
}

/*
 * collapse_spaces
 *
 * Collapses repeated internal whitespace into single spaces in place.
 */
void collapse_spaces(char *str) {
    size_t read_idx = 0;
    size_t write_idx = 0;
    int in_space = 0;

    if (str == NULL) {
        return;
    }

    while (str[read_idx] != '\0') {
        if (isspace((unsigned char)str[read_idx])) {
            if (!in_space) {
                str[write_idx++] = ' ';
                in_space = 1;
            }
        } else {
            str[write_idx++] = str[read_idx];
            in_space = 0;
        }
        read_idx++;
    }

    if (write_idx > 0 && str[write_idx - 1] == ' ') {
        write_idx--;
    }

    str[write_idx] = '\0';
}

/*
 * remove_punctuation
 *
 * Removes punctuation characters from a string in place.
 */
void remove_punctuation(char *str) {
    size_t read_idx = 0;
    size_t write_idx = 0;

    if (str == NULL) {
        return;
    }

    while (str[read_idx] != '\0') {
        if (!ispunct((unsigned char)str[read_idx])) {
            str[write_idx++] = str[read_idx];
        }
        read_idx++;
    }

    str[write_idx] = '\0';
}

/*
 * safe_copy_string
 *
 * Safely copies a string into a fixed-size destination buffer.
 */
void safe_copy_string(char *dest, size_t dest_size, const char *src) {
    if (dest == NULL || src == NULL || dest_size == 0) {
        return;
    }

    strncpy(dest, src, dest_size - 1);
    dest[dest_size - 1] = '\0';
}
