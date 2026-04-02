#include <stddef.h>
#include <string.h>
#include <ctype.h>

#include "utils.h"

/*
 * name_normalizer.c
 *
 * University name normalization helpers.
 *
 * Pipeline: accent_to_ascii → normalize_basic → remove_stopwords → expand_abbreviations
 */

/* Maximum token length for abbreviation/stopword processing */
#define MAX_TOKEN 128
#define MAX_BUF   2048

/*
 * accent_to_ascii
 *
 * Converts known UTF-8 accented characters to their ASCII equivalents.
 * Scans byte-by-byte; handles 2-byte UTF-8 sequences for Latin Extended.
 */
static void accent_to_ascii(const char *input, char *output, int size) {
    int in_pos = 0, out_pos = 0;
    unsigned char c, c2;

    if (!input || !output || size <= 0) return;

    while ((c = (unsigned char)input[in_pos]) != '\0' && out_pos < size - 2) {
        if (c < 0x80) {
            output[out_pos++] = (char)c;
            in_pos++;
            continue;
        }
        /* 2-byte UTF-8: lead byte 0xC0-0xDF */
        c2 = (unsigned char)input[in_pos + 1];
        if ((c & 0xE0) == 0xC0 && c2 != '\0') {
            unsigned int cp = ((c & 0x1F) << 6) | (c2 & 0x3F);
            const char *rep = NULL;
            switch (cp) {
                /* e variants */
                case 0x00E9: case 0x00E8: case 0x00EA: case 0x00EB:
                case 0x00C9: case 0x00C8: case 0x00CA: case 0x00CB:
                    rep = "e"; break;
                /* a variants */
                case 0x00E0: case 0x00E2: case 0x00E4:
                case 0x00C0: case 0x00C2: case 0x00C4:
                    rep = "a"; break;
                /* o variants */
                case 0x00F4: case 0x00F6: case 0x00D4: case 0x00D6:
                case 0x00F8: case 0x00D8:
                    rep = "o"; break;
                /* u variants */
                case 0x00FC: case 0x00F9: case 0x00FB:
                case 0x00DC: case 0x00D9: case 0x00DB:
                    rep = "u"; break;
                /* i variants */
                case 0x00EF: case 0x00EE: case 0x00CF: case 0x00CE:
                    rep = "i"; break;
                /* n tilde */
                case 0x00F1: case 0x00D1: rep = "n"; break;
                /* c cedilla */
                case 0x00E7: case 0x00C7: rep = "c"; break;
                /* sharp s → ss */
                case 0x00DF:
                    if (out_pos < size - 3) {
                        output[out_pos++] = 's';
                        output[out_pos++] = 's';
                    }
                    in_pos += 2; continue;
                /* L stroke */
                case 0x0141: case 0x0142: rep = "l"; break;
                /* a ring */
                case 0x00E5: case 0x00C5: rep = "a"; break;
                /* ae ligature */
                case 0x00E6: case 0x00C6:
                    if (out_pos < size - 3) {
                        output[out_pos++] = 'a';
                        output[out_pos++] = 'e';
                    }
                    in_pos += 2; continue;
                /* oe ligature */
                case 0x0153: case 0x0152:
                    if (out_pos < size - 3) {
                        output[out_pos++] = 'o';
                        output[out_pos++] = 'e';
                    }
                    in_pos += 2; continue;
                default: break;
            }
            if (rep) {
                output[out_pos++] = rep[0];
                in_pos += 2;
                continue;
            }
        }
        /* Unknown multibyte: skip */
        in_pos++;
    }
    output[out_pos] = '\0';
}

/*
 * normalize_basic
 *
 * Trim → remove punctuation → lowercase → collapse spaces.
 */
static void normalize_basic(const char *input, char *output, int size) {
    if (!input || !output || size <= 0) return;
    safe_copy_string(output, (size_t)size, input);
    trim_whitespace(output);
    remove_punctuation(output);
    to_lowercase(output);
    collapse_spaces(output);
    trim_whitespace(output);
}

/*
 * remove_stopwords
 *
 * Tokenizes by space; omits tokens matching common stopwords.
 */
static void remove_stopwords(const char *input, char *output, int size) {
    static const char *stops[] = {
        "the", "of", "and", "for", "a", "an", NULL
    };
    char buf[MAX_BUF];
    char token[MAX_TOKEN];
    int in_pos = 0, out_pos = 0, tok_pos = 0;
    unsigned char c;
    int is_stop, i;

    if (!input || !output || size <= 0) return;
    buf[0] = '\0';

    while (1) {
        c = (unsigned char)input[in_pos];
        if (c == ' ' || c == '\0') {
            if (tok_pos > 0) {
                token[tok_pos] = '\0';
                is_stop = 0;
                for (i = 0; stops[i] != NULL; i++) {
                    if (strcmp(token, stops[i]) == 0) { is_stop = 1; break; }
                }
                if (!is_stop) {
                    if (out_pos > 0 && out_pos < (int)sizeof(buf) - 1)
                        buf[out_pos++] = ' ';
                    int j = 0;
                    while (token[j] && out_pos < (int)sizeof(buf) - 1)
                        buf[out_pos++] = token[j++];
                }
                tok_pos = 0;
            }
            if (c == '\0') break;
        } else {
            if (tok_pos < MAX_TOKEN - 1)
                token[tok_pos++] = (char)c;
        }
        in_pos++;
    }
    buf[out_pos] = '\0';
    safe_copy_string(output, (size_t)size, buf);
}

/*
 * expand_abbreviations
 *
 * Tokenizes by space; expands known academic abbreviations.
 */
static void expand_abbreviations(const char *input, char *output, int size) {
    typedef struct { const char *abbr; const char *full; } AbbrevMap;
    static const AbbrevMap map[] = {
        {"inst",  "institute"},
        {"tech",  "technology"},
        {"univ",  "university"},
        {"natl",  "national"},
        {"intl",  "international"},
        {"coll",  "college"},
        {"sci",   "science"},
        {"engr",  "engineering"},
        {NULL, NULL}
    };
    char buf[MAX_BUF];
    char token[MAX_TOKEN];
    int in_pos = 0, out_pos = 0, tok_pos = 0;
    unsigned char c;
    int i;

    if (!input || !output || size <= 0) return;
    buf[0] = '\0';

    while (1) {
        c = (unsigned char)input[in_pos];
        if (c == ' ' || c == '\0') {
            if (tok_pos > 0) {
                token[tok_pos] = '\0';
                const char *replacement = token;
                for (i = 0; map[i].abbr != NULL; i++) {
                    if (strcmp(token, map[i].abbr) == 0) {
                        replacement = map[i].full;
                        break;
                    }
                }
                if (out_pos > 0 && out_pos < (int)sizeof(buf) - 1)
                    buf[out_pos++] = ' ';
                int j = 0;
                while (replacement[j] && out_pos < (int)sizeof(buf) - 1)
                    buf[out_pos++] = replacement[j++];
                tok_pos = 0;
            }
            if (c == '\0') break;
        } else {
            if (tok_pos < MAX_TOKEN - 1)
                token[tok_pos++] = (char)c;
        }
        in_pos++;
    }
    buf[out_pos] = '\0';
    safe_copy_string(output, (size_t)size, buf);
}

/*
 * normalize_name
 *
 * Full pipeline: accent_to_ascii → normalize_basic → remove_stopwords → expand_abbreviations
 */
void normalize_name(const char *input, char *output, int size) {
    char stage1[MAX_BUF], stage2[MAX_BUF], stage3[MAX_BUF];

    if (input == NULL || output == NULL || size <= 0) {
        return;
    }

    accent_to_ascii(input, stage1, sizeof(stage1));
    normalize_basic(stage1, stage2, sizeof(stage2));
    remove_stopwords(stage2, stage3, sizeof(stage3));
    expand_abbreviations(stage3, output, size);
}