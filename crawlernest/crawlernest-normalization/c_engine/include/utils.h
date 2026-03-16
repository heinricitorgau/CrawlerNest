#ifndef UTILS_H
#define UTILS_H

/*
 * utils.h
 *
 * Common helper functions used across the Clawer C Data Normalization Engine.
 */

#include <stddef.h>

/*
 * trim_whitespace
 *
 * Removes leading and trailing whitespace from a string in place.
 */
void trim_whitespace(char *str);

/*
 * to_lowercase
 *
 * Converts a string to lowercase in place.
 */
void to_lowercase(char *str);

/*
 * collapse_spaces
 *
 * Collapses repeated internal whitespace into single spaces in place.
 */
void collapse_spaces(char *str);

/*
 * remove_punctuation
 *
 * Removes punctuation characters from a string in place.
 */
void remove_punctuation(char *str);

/*
 * safe_copy_string
 *
 * Safely copies a string into a fixed-size destination buffer.
 */
void safe_copy_string(char *dest, size_t dest_size, const char *src);

#endif /* UTILS_H */
