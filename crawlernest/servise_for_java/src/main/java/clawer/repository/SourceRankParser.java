package clawer.repository;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;

class SourceRankParser {
    private final ObjectMapper objectMapper;

    SourceRankParser(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    Map<String, Integer> parse(Object value) {
        if (value == null) {
            return new LinkedHashMap<>();
        }
        try {
            Map<String, Object> raw = objectMapper.readValue(value.toString(), new TypeReference<>() {});
            Map<String, Integer> parsed = new LinkedHashMap<>();
            for (Map.Entry<String, Object> entry : raw.entrySet()) {
                if (entry.getValue() != null) {
                    Integer normalizedRank = toIntegerRank(entry.getValue());
                    if (normalizedRank != null) {
                        parsed.put(entry.getKey().toUpperCase(Locale.ROOT), normalizedRank);
                    }
                }
            }
            return parsed;
        } catch (Exception e) {
            return new LinkedHashMap<>();
        }
    }

    private Integer toIntegerRank(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Number number) {
            return (int) Math.round(number.doubleValue());
        }
        try {
            return (int) Math.round(Double.parseDouble(value.toString()));
        } catch (NumberFormatException ex) {
            return null;
        }
    }
}
