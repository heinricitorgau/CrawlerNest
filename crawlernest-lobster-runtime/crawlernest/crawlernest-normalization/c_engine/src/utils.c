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
 * is_acronym
 *
 * Checks if a word matches known uppercase acronyms.
 */
static int is_acronym(const char *word, size_t len) {
    const char *acronyms[] = {"MIT", "UCL", "NUS", "NTU", "USA", "UK", "SG", "ROC", "NYU", "UCLA", "UCB", "UCSD", "ANU", "UNSW", "CUHK", "EPFL", "KAIST", "POSTECH", "LSE", "KTH", "UM", "UBA", "UNAM", "UC", "NTU", "UM", "LSE", NULL};
    char temp[32];
    int i;
    
    if (len >= sizeof(temp)) return 0;
    
    for (size_t j = 0; j < len; j++) {
        temp[j] = (char)toupper((unsigned char)word[j]);
    }
    temp[len] = '\0';
    
    for (i = 0; acronyms[i] != NULL; i++) {
        if (strcmp(temp, acronyms[i]) == 0) {
            return 1;
        }
    }
    return 0;
}

/*
 * process_word_case
 *
 * Applies Title Case, lowercase (for 'of'), or uppercase (for acronyms).
 */
static void process_word_case(char *start, size_t len, int is_first_word) {
    if (len == 0) return;
    
    if (len == 2 && tolower((unsigned char)start[0]) == 'o' && tolower((unsigned char)start[1]) == 'f') {
        if (!is_first_word) {
            start[0] = 'o';
            start[1] = 'f';
            return;
        }
    }
    
    if (is_acronym(start, len)) {
        for (size_t i = 0; i < len; i++) {
            start[i] = (char)toupper((unsigned char)start[i]);
        }
        return;
    }
    
    /* Default Title Case */
    start[0] = (char)toupper((unsigned char)start[0]);
    for (size_t i = 1; i < len; i++) {
        start[i] = (char)tolower((unsigned char)start[i]);
    }
}

/*
 * to_title_case
 *
 * Converts a string to Title Case in place, respecting acronyms and 'of'.
 */
void to_title_case(char *str) {
    char *word_start = NULL;
    int is_first = 1;

    if (str == NULL) {
        return;
    }

    for (size_t i = 0; str[i] != '\0'; i++) {
        if (isalpha((unsigned char)str[i])) {
            if (word_start == NULL) {
                word_start = &str[i];
            }
        } else {
            if (word_start != NULL) {
                process_word_case(word_start, &str[i] - word_start, is_first);
                is_first = 0;
                word_start = NULL;
            }
        }
    }
    
    if (word_start != NULL) {
        process_word_case(word_start, strlen(word_start), is_first);
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
 * Removes punctuation characters from a string in place, EXCEPT parentheses.
 */
void remove_punctuation(char *str) {
    size_t read_idx = 0;
    size_t write_idx = 0;
    char c;

    if (str == NULL) {
        return;
    }

    while ((c = str[read_idx]) != '\0') {
        if (!ispunct((unsigned char)c) || c == '(' || c == ')') {
            str[write_idx++] = c;
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
