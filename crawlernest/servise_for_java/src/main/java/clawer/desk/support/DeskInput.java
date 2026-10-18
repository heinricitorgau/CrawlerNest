package clawer.desk.support;

import com.fasterxml.jackson.databind.JsonNode;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.Iterator;
import java.util.Set;

/**
 * Reads one JSON request body field by field.
 *
 * <p>Bodies are read as a tree rather than bound to a class because a PATCH has
 * to tell "field absent" (leave it alone) from "field null" (clear it), which a
 * bound object cannot. Each reader returns null for both, so a caller that
 * cares asks {@link #has} first.
 *
 * <p>Unknown fields are refused rather than ignored: a misspelt {@code dueDte}
 * silently doing nothing is worse than a 400 that names it.
 */
public final class DeskInput {

    private final JsonNode body;

    public DeskInput(JsonNode body, Set<String> allowedFields) {
        if (body == null || !body.isObject()) {
            throw DeskException.badRequest("Body must be a JSON object.");
        }
        for (Iterator<String> names = body.fieldNames(); names.hasNext(); ) {
            String name = names.next();
            if (!allowedFields.contains(name)) {
                throw DeskException.badRequest("Unknown field: " + name + ".");
            }
        }
        this.body = body;
    }

    public boolean has(String field) {
        return body.has(field);
    }

    private JsonNode value(String field) {
        JsonNode node = body.get(field);
        return node == null || node.isNull() ? null : node;
    }

    /** Trimmed text, or null. Blank counts as absent. */
    public String text(String field, int maxLength, boolean required) {
        JsonNode node = value(field);
        if (node == null) {
            if (required) throw DeskException.badRequest(field + " is required.");
            return null;
        }
        if (!node.isTextual()) {
            throw DeskException.badRequest(field + " must be a string.");
        }
        String text = node.asText().trim();
        if (text.isEmpty()) {
            if (required) throw DeskException.badRequest(field + " is required.");
            return null;
        }
        if (text.length() > maxLength) {
            throw DeskException.badRequest(field + " must be " + maxLength + " characters or fewer.");
        }
        return text;
    }

    public String oneOf(String field, Set<String> allowed, boolean required) {
        String text = text(field, 40, required);
        if (text != null && !allowed.contains(text)) {
            throw DeskException.badRequest(field + " must be one of " + String.join(", ", allowed.stream().sorted().toList()) + ".");
        }
        return text;
    }

    /** An ISO calendar date, YYYY-MM-DD. */
    public LocalDate date(String field, boolean required) {
        String text = text(field, 10, required);
        if (text == null) return null;
        try {
            return LocalDate.parse(text);
        } catch (DateTimeParseException e) {
            throw DeskException.badRequest(field + " must be a date in YYYY-MM-DD form.");
        }
    }

    public Long id(String field, boolean required) {
        JsonNode node = value(field);
        if (node == null) {
            if (required) throw DeskException.badRequest(field + " is required.");
            return null;
        }
        if (!node.canConvertToLong() || !node.isIntegralNumber() || node.asLong() <= 0) {
            throw DeskException.badRequest(field + " must be a positive integer.");
        }
        return node.asLong();
    }

    public Integer integer(String field, int min, int max, boolean required) {
        JsonNode node = value(field);
        if (node == null) {
            if (required) throw DeskException.badRequest(field + " is required.");
            return null;
        }
        if (!node.isIntegralNumber() || !node.canConvertToInt() || node.asInt() < min || node.asInt() > max) {
            throw DeskException.badRequest(field + " must be a whole number from " + min + " to " + max + ".");
        }
        return node.asInt();
    }

    public BigDecimal decimal(String field, BigDecimal min, BigDecimal max) {
        JsonNode node = value(field);
        if (node == null) return null;
        if (!node.isNumber()) {
            throw DeskException.badRequest(field + " must be a number.");
        }
        BigDecimal number = node.decimalValue();
        if (number.compareTo(min) < 0 || number.compareTo(max) > 0) {
            throw DeskException.badRequest(field + " must be between " + min.toPlainString() + " and " + max.toPlainString() + ".");
        }
        return number;
    }

    /** The raw node, for the one JSON-object field (profile preferences). */
    public JsonNode node(String field) {
        return value(field);
    }
}
