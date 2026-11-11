package clawer.service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** Every point says what it is; the two kinds of gap never look alike. */
class RankHistoryServiceTest {

    private static Map<String, Object> row(int rank, String display, String entity) {
        Map<String, Object> row = new HashMap<>();
        row.put("rank_position", rank);
        row.put("rank_display", display);
        row.put("source_entity_id", entity);
        row.put("suspicious_merge", false);
        return row;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> point(Map<String, Object> data, String source, int year) {
        for (Map<String, Object> series : (List<Map<String, Object>>) data.get("series")) {
            if (source.equals(series.get("source"))) {
                for (Map<String, Object> point : (List<Map<String, Object>>) series.get("points")) {
                    if (((Integer) point.get("year")) == year) {
                        return point;
                    }
                }
            }
        }
        throw new AssertionError(source + " " + year + " missing");
    }

    @Test
    void gapsAreLabelledAsNotHeldOrNotInTheEdition() {
        Map<String, Map<Integer, Map<String, Object>>> rows = new HashMap<>();
        rows.put("THE", new HashMap<>(Map.of(2026, row(5, "5", "the:x"), 2024, row(201, "201-250", "the:x"))));
        rows.put("QS", new HashMap<>(Map.of(2026, row(3, "=3", "qs:y"))));

        Map<String, Object> data = RankHistoryService.build(List.of(2026, 2025, 2024, 2016), rows);

        assertEquals(List.of(2016, 2024, 2025, 2026), data.get("years"));
        assertEquals("ranked", point(data, "THE", 2026).get("status"));
        assertEquals("not_in_edition", point(data, "THE", 2025).get("status"));
        Map<String, Object> banded = point(data, "THE", 2024);
        assertEquals(201, banded.get("rankLower"));
        assertEquals(250, banded.get("rankUpper"));
        assertEquals("201-250", banded.get("rankDisplay"));

        // QS holds no 2016 edition at all: that is not this university's gap.
        assertEquals("edition_not_held", point(data, "QS", 2016).get("status"));
        assertEquals(3, point(data, "QS", 2026).get("rankLower"));
        // ARWU holds every one of these editions, and this university is in none of them here.
        assertEquals("not_in_edition", point(data, "ARWU", 2026).get("status"));

        List<String> caveats = (List<String>) data.get("caveats");
        assertEquals(AnalyticsService.RANK_HISTORY_CAVEAT, caveats.get(0));
        assertTrue(caveats.contains(AnalyticsService.THE_PARTIAL_CAVEAT));
        assertFalse(caveats.contains(AnalyticsService.ARWU_PARTIAL_CAVEAT));
    }

    @Test
    void anArchivedEditionCarriesItsCaveatAndAChangedSourceEntryIsMarked() {
        Map<String, Map<Integer, Map<String, Object>>> rows = new HashMap<>();
        rows.put("QS", new HashMap<>(Map.of(
                2023, row(100, "100", "qs:2023:a"),
                2024, row(90, "90", "qs:2024:a"),
                2025, row(80, "80", "qs:2025:b"))));

        Map<String, Object> data = RankHistoryService.build(List.of(2023, 2024, 2025), rows);

        assertEquals(true, point(data, "QS", 2023).get("archived"));
        assertEquals(false, point(data, "QS", 2025).get("archived"));
        assertTrue(((List<String>) data.get("caveats")).contains(AnalyticsService.archiveEditionCaveat("QS", 2023)));
        // The year segment is not an identity change; a different entry is.
        assertEquals(false, point(data, "QS", 2024).get("sourceIdentityChanged"));
        assertEquals(true, point(data, "QS", 2025).get("sourceIdentityChanged"));
    }

    @Test
    void anOpenBandHasNoUpperBound() {
        Map<String, Map<Integer, Map<String, Object>>> rows = new HashMap<>();
        rows.put("ARWU", new HashMap<>(Map.of(2026, row(901, "901-1000", null), 2025, row(1001, "1001+", null))));
        Map<String, Object> data = RankHistoryService.build(List.of(2025, 2026), rows);
        assertNull(point(data, "ARWU", 2025).get("rankUpper"));
        assertEquals(1001, point(data, "ARWU", 2025).get("rankLower"));
    }
}
