package clawer.service;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Centralized country alias normalization for product filtering.
 * This keeps query semantics stable even when source systems emit country-name variants.
 */
public final class CountryNormalization {
    private static final Map<String, List<String>> CANONICAL_ALIASES = new LinkedHashMap<>();

    static {
        CANONICAL_ALIASES.put("China", List.of(
                "china",
                "china mainland"
        ));
        CANONICAL_ALIASES.put("United States", List.of(
                "united states",
                "united states of america",
                "usa",
                "us",
                "u s",
                "u s a"
        ));
        CANONICAL_ALIASES.put("United Kingdom", List.of(
                "united kingdom",
                "uk",
                "u k",
                "great britain",
                "britain"
        ));
        CANONICAL_ALIASES.put("Hong Kong", List.of(
                "hong kong",
                "hong kong sar",
                "hong kong sar china",
                "hong kong sar china"
        ));
        CANONICAL_ALIASES.put("Macau", List.of(
                "macau",
                "macao",
                "macau sar",
                "macao sar"
        ));
        CANONICAL_ALIASES.put("Russia", List.of(
                "russia",
                "russian federation"
        ));
    }

    private CountryNormalization() {}

    public static String normalizeCountry(String input) {
        String cleaned = cleanCountry(input);
        if (cleaned == null) {
            return null;
        }

        for (Map.Entry<String, List<String>> entry : CANONICAL_ALIASES.entrySet()) {
            if (entry.getValue().contains(cleaned)) {
                return entry.getKey();
            }
        }

        return toDisplayName(cleaned);
    }

    public static String canonicalCountrySqlExpression(String columnExpression) {
        String cleanedExpression = "trim(regexp_replace(replace(replace(replace(replace(lower(coalesce(" + columnExpression + ", '')), '.', ''), '&', ' and '), '(', ' '), ')', ' '), '\\\\s+', ' ', 'g'))";
        StringBuilder sql = new StringBuilder("CASE ");
        for (Map.Entry<String, List<String>> entry : CANONICAL_ALIASES.entrySet()) {
            sql.append("WHEN ")
                    .append(cleanedExpression)
                    .append(" IN (");
            for (int i = 0; i < entry.getValue().size(); i++) {
                if (i > 0) {
                    sql.append(", ");
                }
                sql.append('\'')
                        .append(entry.getValue().get(i).replace("'", "''"))
                        .append('\'');
            }
            sql.append(") THEN '")
                    .append(entry.getKey().replace("'", "''"))
                    .append("' ");
        }
        sql.append("ELSE initcap(")
                .append(cleanedExpression)
                .append(") END");
        return sql.toString();
    }

    private static String cleanCountry(String input) {
        if (input == null) {
            return null;
        }

        String normalized = input
                .trim()
                .replace("&", " and ")
                .replace(".", "")
                .replace("(", " ")
                .replace(")", " ")
                .replaceAll("\\s+", " ")
                .trim();

        if (normalized.isEmpty()) {
            return null;
        }

        return normalized.toLowerCase(Locale.ROOT);
    }

    private static String toDisplayName(String cleaned) {
        String[] tokens = cleaned.split(" ");
        StringBuilder display = new StringBuilder();
        for (String token : tokens) {
            if (display.length() > 0) {
                display.append(' ');
            }
            if (token.isEmpty()) {
                continue;
            }
            display.append(Character.toUpperCase(token.charAt(0)));
            if (token.length() > 1) {
                display.append(token.substring(1));
            }
        }
        return display.toString();
    }
}
