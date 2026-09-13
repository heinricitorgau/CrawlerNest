package clawer.service;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * The source-coverage caveats must be derived from the warehouse, not stated.
 *
 * These used to be constants: "THE data is not available", "all universities have
 * single-source (QS-only) coverage". Both were true when written and both became
 * false the day THE was ingested for part of the table -- a disclosure that is
 * specific, confident and wrong, which is worse than none.
 *
 * The sentence these tests care about most is the one about what a *missing*
 * rank means. A null is ambiguous: the source may not rank the university, or
 * this platform may have failed to match it. Only the second is our doing, and
 * reporting it as the first blames the institution for our gap.
 */
class SourceCoverageCaveatTest {

    /** An AnalyticsService whose warehouse reports the given per-source counts. */
    private AnalyticsService serviceReporting(int qs, int the, int arwu) {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        // The third argument is the edition the coverage is counted in.
        int edition = DatasetScope.DEFAULT_RANKING_YEAR;
        when(jdbc.queryForObject(anyString(), eq(Integer.class), eq("QS"), eq("QS"), eq(edition))).thenReturn(qs);
        when(jdbc.queryForObject(anyString(), eq(Integer.class), eq("THE"), eq("THE"), eq(edition))).thenReturn(the);
        when(jdbc.queryForObject(anyString(), eq(Integer.class), eq("ARWU"), eq("ARWU"), eq(edition))).thenReturn(arwu);
        return new AnalyticsService(jdbc, new com.fasterxml.jackson.databind.ObjectMapper());
    }

    private List<String> caveatsFor(int qs, int the, int arwu) {
        List<String> caveats = new ArrayList<>();
        serviceReporting(qs, the, arwu).appendSourceCoverageCaveats(caveats);
        return caveats;
    }

    @Test
    @DisplayName("a partially covered source says a missing rank is our gap, not the source's")
    void partialCoverageExplainsWhatANullMeans() {
        List<String> caveats = caveatsFor(1499, 969, 0);

        String theCaveat = caveats.stream()
                .filter(c -> c.startsWith("THE ("))
                .findFirst()
                .orElseThrow(() -> new AssertionError("no caveat for the partially covered source"));

        assertTrue(theCaveat.contains("969 of 1499"),
                "the caveat must give the real coverage, not a description of it: " + theCaveat);
        assertTrue(theCaveat.contains("does not include the university"),
                "the caveat must offer the partial-snapshot cause: for ARWU, whose snapshot "
                        + "holds its top 30, that is the usual reason a rank is missing");
        assertTrue(theCaveat.contains("could not match"),
                "the caveat must also offer the failed-match cause; both are ours");
        assertTrue(theCaveat.contains("not that THE does not rank it"),
                "the caveat must rule out the reading that the source declined to rank: " + theCaveat);
    }

    @Test
    @DisplayName("a source with no rows is reported as absent, not as partial")
    void absentSourceIsReportedAsAbsent() {
        List<String> caveats = caveatsFor(1499, 969, 0);

        String arwu = caveats.stream()
                .filter(c -> c.startsWith("ARWU ("))
                .findFirst()
                .orElseThrow(() -> new AssertionError("no caveat for the absent source"));

        assertTrue(arwu.contains("not available"), arwu);
        assertFalse(arwu.contains("could not match"),
                "an absent source has nothing to fail to match against: " + arwu);
    }

    @Test
    @DisplayName("a fully covered source gets no coverage caveat")
    void fullCoverageIsSilent() {
        List<String> caveats = caveatsFor(1499, 969, 0);

        assertTrue(caveats.stream().noneMatch(c -> c.startsWith("QS (")),
                "QS covers every row, so there is nothing to disclose about it: " + caveats);
    }

    @Test
    @DisplayName("the caveats change when the coverage changes")
    void caveatsTrackTheData() {
        List<String> before = caveatsFor(1499, 0, 0);
        List<String> after = caveatsFor(1499, 969, 0);

        assertTrue(before.stream().anyMatch(c -> c.startsWith("THE (") && c.contains("not available")),
                "with no THE rows the caveat must say the source is absent: " + before);
        assertTrue(after.stream().anyMatch(c -> c.startsWith("THE (") && c.contains("969 of 1499")),
                "with THE rows the caveat must report the coverage: " + after);
        assertFalse(before.equals(after),
                "a hardcoded caveat would produce the same text for both warehouses");
    }

    @Test
    @DisplayName("sources are listed in a fixed order")
    void orderIsStable() {
        // Map.of does not preserve order, so this fails if the declaration goes
        // back to being a Map -- a caveats array that reshuffles between restarts
        // is hard to diff and hard to hold a contract against.
        List<String> caveats = caveatsFor(1499, 969, 0);
        List<String> sourcesInOrder = caveats.stream()
                .map(c -> c.substring(0, c.indexOf(' ')))
                .toList();
        assertEquals(List.of("THE", "ARWU"), sourcesInOrder,
                "QS is silent at full coverage; the rest must follow the declared order");
    }
}
