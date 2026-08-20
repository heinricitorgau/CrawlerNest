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
    size_t k;

    if (input == NULL || output == NULL || size <= 0) {
        return;
    }

    safe_copy_string(output, (size_t)size, input);
    trim_whitespace(output);

    /*
     * Fix E (Session 3): replace hyphens with spaces BEFORE remove_punctuation
     * so that "Timor-Leste" → "Timor Leste" instead of "Timorleste".
     * remove_punctuation deletes all ispunct except parentheses, which
     * includes hyphens; substituting first preserves word boundaries.
     */
    for (k = 0; output[k] != '\0'; k++) {
        if (output[k] == '-') {
            output[k] = ' ';
        }
    }

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
        {"britain", "United Kingdom"},
        {"england", "United Kingdom"},
        {"scotland", "United Kingdom"},
        {"wales", "United Kingdom"},
        {"northern ireland", "United Kingdom"},
        {"sg", "Singapore"},
        {"singapore", "Singapore"},
        {"china mainland", "China (Mainland)"},
        {"mainland china", "China (Mainland)"},
        {"prc", "China (Mainland)"},
        {"peoples republic of china", "China (Mainland)"},
        {"china", "China (Mainland)"},
        {"hong kong sar", "Hong Kong SAR"},
        {"hong kong", "Hong Kong SAR"},
        {"taiwan", "Taiwan"},
        {"republic of china", "Taiwan"},
        {"roc", "Taiwan"},
        {"south korea", "South Korea"},
        {"korea", "South Korea"},
        {"republic of korea", "South Korea"},
        {"korea republic of", "South Korea"},   /* 倒裝變體 */
        {"korea south", "South Korea"},          /* 形容詞後置 */
        {"north korea", "North Korea"},
        {"dprk", "North Korea"},
        {"democratic peoples republic of korea", "North Korea"},
        {"my", "Malaysia"},
        {"malaysia", "Malaysia"},
        {"uae", "United Arab Emirates"},
        {"united arab emirates", "United Arab Emirates"},
        {"au", "Australia"},
        {"australia", "Australia"},
        {"ca", "Canada"},
        {"canada", "Canada"},
        {"de", "Germany"},
        {"germany", "Germany"},
        {"fr", "France"},
        {"france", "France"},
        {"jp", "Japan"},
        {"japan", "Japan"},
        {"ch", "Switzerland"},
        {"switzerland", "Switzerland"},
        {"se", "Sweden"},
        {"sweden", "Sweden"},
        {"nl", "Netherlands"},
        {"netherlands", "Netherlands"},
        {"be", "Belgium"},
        {"belgium", "Belgium"},
        {"nz", "New Zealand"},
        {"new zealand", "New Zealand"},
        /* Fix E (Session 3): hyphenated country names — stored without hyphens
         * because normalize_basic now converts hyphens to spaces before lookup */
        {"timor leste", "Timor-Leste"},
        {"east timor", "Timor-Leste"},
        {"guinea bissau", "Guinea-Bissau"},
        {"trinidad and tobago", "Trinidad and Tobago"},
        {"antigua and barbuda", "Antigua and Barbuda"},
        {"bosnia and herzegovina", "Bosnia and Herzegovina"},
        {"sao tome and principe", "São Tomé and Príncipe"},
        {"cabo verde", "Cabo Verde"},
        {"sierra leone", "Sierra Leone"},
        {"saudi arabia", "Saudi Arabia"},
        {"united states minor outlying islands", "United States"},
        /*
         * Fix R (Session 6): "The X" prefix variants and PR China aliases.
         *
         * Many official and colloquial forms prepend "The" or use abbreviated
         * forms ("PR China") that normalize_basic cannot collapse into an
         * existing entry.  These are all stored in their post-normalize_basic
         * form (lowercase, no punctuation, spaces collapsed).
         */
        /* "The X" prefix variants */
        {"the netherlands", "Netherlands"},
        {"the united states", "United States"},
        {"the united states of america", "United States"},
        {"the united kingdom", "United Kingdom"},
        {"the peoples republic of china", "China (Mainland)"},
        /* PR China — P.R. China / P.R.C. collapses to "pr china" after
         * remove_punctuation; "prc" already handled above */
        {"pr china", "China (Mainland)"},
        /* Long-form official names commonly seen in UN / World Bank data */
        {"republic of india", "India"},
        {"federal republic of germany", "Germany"},
        {"kingdom of saudi arabia", "Saudi Arabia"},
        {"swiss confederation", "Switzerland"},
        {"hellenic republic", "Greece"},
        {"republic of greece", "Greece"},
        {"republic of south africa", "South Africa"},
        {"kingdom of the netherlands", "Netherlands"},
        {"islamic republic of pakistan", "Pakistan"},
        {"federative republic of brazil", "Brazil"},
        {"kingdom of spain", "Spain"},
        {"kingdom of norway", "Norway"},
        {"kingdom of denmark", "Denmark"},
        {"republic of austria", "Austria"},
        {"republic of ireland", "Ireland"},
        {"republic of poland", "Poland"},
        {"republic of italy", "Italy"},
        {"republic of portugal", "Portugal"},
        {"republic of finland", "Finland"},
        {"kingdom of belgium", "Belgium"},
        {"kingdom of sweden", "Sweden"},
        {"republic of singapore", "Singapore"},
        {"republic of indonesia", "Indonesia"},
        {"republic of turkey", "Turkey"},
        {"republic of the philippines", "Philippines"},
        {"philippines", "Philippines"},
        {"republic of france", "France"},
        {"grand duchy of luxembourg", "Luxembourg"},
        {"luxembourg", "Luxembourg"},
        /* Fix J (Session 4): additional aliases commonly seen in ranking data */
        /* Korea short-form variants after punctuation removal */
        {"korea rep", "South Korea"},
        {"korea republic", "South Korea"},
        {"dem peoples rep of korea", "North Korea"},
        {"korea dem peoples rep", "North Korea"},
        {"korea democratic peoples republic", "North Korea"},
        /* Russia / Soviet-era names */
        {"russia", "Russia"},
        {"russian federation", "Russia"},
        {"ussr", "Russia"},
        /* Macao/Macau — two common spellings, canonical: "Macao SAR" */
        {"macao", "Macao SAR"},
        {"macau", "Macao SAR"},
        {"macao sar", "Macao SAR"},
        {"macau sar", "Macao SAR"},
        /* Czech Republic / Czechia */
        {"czech republic", "Czech Republic"},
        {"czechia", "Czech Republic"},
        /* Iran */
        {"iran", "Iran"},
        {"islamic republic of iran", "Iran"},
        /* Turkey/Türkiye */
        {"turkey", "Turkey"},
        {"turkiye", "Turkey"},
        /* Vietnam */
        {"vietnam", "Vietnam"},
        {"viet nam", "Vietnam"},
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