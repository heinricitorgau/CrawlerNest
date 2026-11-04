package clawer.desk.chat;

import clawer.dto.UsInstitutionDTO;
import clawer.repository.UsInstitutionRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.text.DecimalFormat;
import java.text.DecimalFormatSymbols;
import java.util.List;
import java.util.Locale;
import java.util.Optional;

/**
 * Tassel's one read-only tool, {@code lookup_us_federal_data}: the College Scorecard and
 * IPEDS figures for a school on the student's list.
 *
 * <p>Unlike the tools in {@link TasselToolExecutor} it changes nothing, so it is not recorded
 * in {@code desk.chat_action} and has nothing to confirm or undo. It is reached only through
 * the student's own target row, and only when that row links a warehouse university: a
 * school is never looked up by name. Every successful lookup carries the caveats of the
 * figures it returned, which the chat response passes on to the desk.
 */
@Component
public class TasselFederalLookup {

    public static final String TOOL = "lookup_us_federal_data";

    /**
     * What one lookup came to. {@code status} is "found", "none" (no federal record) or "failed".
     * {@code forModel} is the tool message the model reads; {@code caveats} is empty unless found.
     */
    public record Result(String tool, String status, Long targetEntityId, Long canonicalUniversityId, Integer unitid,
                         String message, ObjectNode forModel, List<String> caveats) {}

    /** Sent with every found result, so the model has the rules beside the figures it is about to quote. */
    static final String QUOTING_RULES = "Quote each figure with its period; the periods differ by years. A figure"
            + " that is withheld or not available is not zero: say so. These are federal statistics, not rankings,"
            + " and an admission rate is not this student's chance of admission.";

    private final JdbcTemplate jdbc;
    private final UsInstitutionRepository repository;
    private final ObjectMapper objectMapper;

    public TasselFederalLookup(JdbcTemplate jdbc, UsInstitutionRepository repository, ObjectMapper objectMapper) {
        this.jdbc = jdbc;
        this.repository = repository;
        this.objectMapper = objectMapper;
    }

    public Result lookup(long userId, String rawArguments) {
        JsonNode args;
        try {
            args = objectMapper.readTree(rawArguments == null || rawArguments.isBlank() ? "{}" : rawArguments);
        } catch (Exception e) {
            args = null;
        }
        JsonNode id = args == null ? null : args.get("targetEntityId");
        if (id == null || !id.canConvertToLong() || !id.isIntegralNumber() || id.asLong() <= 0) {
            return failed(null, "targetEntityId must be the id of a school on the student's list. " + listOfSchools(userId));
        }
        long targetId = id.asLong();
        List<Object[]> rows = jdbc.query("""
                SELECT t.canonical_university_id, coalesce(cu.display_name, t.custom_name) AS name
                FROM desk.target_entity t
                LEFT JOIN warehouse.canonical_university cu ON cu.canonical_university_id = t.canonical_university_id
                WHERE t.id = ? AND t.user_id = ?
                """, (rs, n) -> new Object[]{rs.getObject("canonical_university_id", Long.class), rs.getString("name")},
                targetId, userId);
        if (rows.isEmpty()) {
            return failed(targetId, "There is no school with id " + targetId + " on the list. " + listOfSchools(userId));
        }
        Long canonicalId = (Long) rows.get(0)[0];
        String name = (String) rows.get(0)[1];
        if (canonicalId == null) {
            return none(targetId, null, name + " is on the list by name only, not linked to a CrawlerNest university,"
                    + " so no federal record can be looked up for it.");
        }
        Optional<UsInstitutionDTO> record = repository.findByCanonicalUniversityId(canonicalId);
        if (record.isEmpty()) {
            return none(targetId, canonicalId, "CrawlerNest has no US federal record matched to " + name + ". The school"
                    + " may be outside the US, or not matched; that says nothing about the school.");
        }
        UsInstitutionDTO data = record.get();
        ObjectNode out = objectMapper.createObjectNode();
        out.put("status", "found");
        out.put("school", name);
        out.put("federalRecord", data.institutionName());
        out.put("unitid", data.unitid());
        ArrayNode figures = out.putArray("figures");
        for (UsInstitutionDTO.Metric m : data.metrics()) {
            if ("not_applicable".equals(m.status())) {
                continue;
            }
            ObjectNode f = figures.addObject();
            f.put("figure", m.key());
            String shown = display(m);
            if (shown == null) {
                f.putNull("value");
            } else {
                f.put("value", shown);
            }
            f.put("status", m.status());
            if (m.statusDetail() != null && !"reported".equals(m.status())) {
                f.put("detail", m.statusDetail());
            }
            f.put("period", m.referencePeriod());
            f.put("source", "COLLEGE_SCORECARD".equals(m.source()) ? "College Scorecard" : m.source());
        }
        ArrayNode caveats = out.putArray("caveats");
        data.caveats().forEach(caveats::add);
        out.put("rules", QUOTING_RULES);
        return new Result(TOOL, "found", targetId, canonicalId, data.unitid(),
                "Read the US federal figures for " + name + ".", out, data.caveats());
    }

    /** The figure as the page shows it, so the model never formats a ratio itself; null when there is none. */
    static String display(UsInstitutionDTO.Metric m) {
        boolean hasFigure = "reported".equals(m.status()) || "imputed".equals(m.status());
        if (!hasFigure) {
            return null;
        }
        if ("code".equals(m.unit()) || "text".equals(m.unit())) {
            return m.valueText() != null ? m.valueText() : (m.value() == null ? null : m.value().toPlainString());
        }
        BigDecimal v = m.value();
        if (v == null) {
            return null;
        }
        DecimalFormatSymbols us = DecimalFormatSymbols.getInstance(Locale.US);
        return switch (m.unit()) {
            case "ratio" -> new DecimalFormat("#,##0.#", us).format(v.multiply(BigDecimal.valueOf(100))) + "%";
            case "percent" -> new DecimalFormat("#,##0.#", us).format(v) + "%";
            case "usd" -> "$" + new DecimalFormat("#,##0", us).format(v.setScale(0, RoundingMode.HALF_UP));
            default -> new DecimalFormat("#,##0.##", us).format(v);
        };
    }

    private String listOfSchools(long userId) {
        List<String> schools = jdbc.query("""
                SELECT t.id, coalesce(cu.display_name, t.custom_name) AS name
                FROM desk.target_entity t
                LEFT JOIN warehouse.canonical_university cu ON cu.canonical_university_id = t.canonical_university_id
                WHERE t.user_id = ? ORDER BY t.id LIMIT 20
                """, (rs, n) -> "[" + rs.getLong("id") + "] " + rs.getString("name"), userId);
        return schools.isEmpty() ? "The list is empty." : "The list: " + String.join(", ", schools) + ".";
    }

    private Result none(Long targetId, Long canonicalId, String message) {
        ObjectNode out = objectMapper.createObjectNode();
        out.put("status", "none");
        out.put("message", message);
        out.put("rules", "Do not fill the gap from memory.");
        return new Result(TOOL, "none", targetId, canonicalId, null, message, out, List.of());
    }

    private Result failed(Long targetId, String message) {
        ObjectNode out = objectMapper.createObjectNode();
        out.put("status", "failed");
        out.put("message", message);
        out.put("next", "Take the right id from the context and call again, once. Never ask the student for an id.");
        return new Result(TOOL, "failed", targetId, null, null, message, out, List.of());
    }
}
