package clawer.util;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class CountryNormalization {
    private static final Map<String, String> ALIAS_TO_CANONICAL = buildAliasMap();

    private CountryNormalization() {}

    public static String normalizeCountry(String input) {
        String key = normalizeKey(input);
        if (key == null) {
            return null;
        }
        return ALIAS_TO_CANONICAL.getOrDefault(key, toTitleCase(input));
    }

    public static String canonicalSqlExpression(String column) {
        String normalizedColumn = "regexp_replace(lower(btrim(coalesce(" + column + ", ''))), '\\s+', ' ', 'g')";
        StringBuilder sql = new StringBuilder("CASE ");

        Map<String, List<String>> canonicalGroups = new LinkedHashMap<>();
        canonicalGroups.put("China", List.of("china", "china (mainland)", "china mainland"));
        canonicalGroups.put("United States", List.of("united states", "united states of america", "usa", "us", "u.s."));
        canonicalGroups.put("United Kingdom", List.of("united kingdom", "uk", "u.k.", "great britain"));

        for (Map.Entry<String, List<String>> entry : canonicalGroups.entrySet()) {
            sql.append("WHEN ")
                    .append(normalizedColumn)
                    .append(" IN (")
                    .append(entry.getValue().stream()
                            .map(alias -> "'" + alias.replace("'", "''") + "'")
                            .reduce((left, right) -> left + ", " + right)
                            .orElse(""))
                    .append(") THEN '")
                    .append(entry.getKey().replace("'", "''"))
                    .append("' ");
        }

        sql.append("ELSE initcap(").append(normalizedColumn).append(") END");
        return sql.toString();
    }

    private static Map<String, String> buildAliasMap() {
        Map<String, String> aliases = new LinkedHashMap<>();
        register(aliases, "China", "china", "china (mainland)", "china mainland");
        register(aliases, "United States", "united states", "united states of america", "usa", "us", "u.s.");
        register(aliases, "United Kingdom", "united kingdom", "uk", "u.k.", "great britain");
        return aliases;
    }

    private static void register(Map<String, String> aliases, String canonical, String... variants) {
        aliases.put(normalizeKey(canonical), canonical);
        for (String variant : variants) {
            aliases.put(normalizeKey(variant), canonical);
        }
    }

    private static String normalizeKey(String input) {
        if (input == null) {
            return null;
        }
        String normalized = input.trim().replaceAll("\\s+", " ").toLowerCase();
        return normalized.isEmpty() ? null : normalized;
    }

    private static String toTitleCase(String input) {
        String normalized = normalizeKey(input);
        if (normalized == null) {
            return null;
        }
        String[] parts = normalized.split(" ");
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < parts.length; i++) {
            if (i > 0) {
                builder.append(' ');
            }
            String part = parts[i];
            if (part.isEmpty()) {
                continue;
            }
            builder.append(Character.toUpperCase(part.charAt(0)));
            if (part.length() > 1) {
                builder.append(part.substring(1));
            }
        }
        return builder.toString();
    }
}
