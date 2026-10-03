package clawer.service;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Guards the model-estimate caveat contract.
 *
 * The root CLAUDE.md warns that caveat strings live in more than one place and
 * that changing one usually means changing all of them. For this caveat the code
 * duplication is removed -- AnalyticsController references
 * {@link AnalyticsService#ESTIMATED_SCORE_CAVEAT} -- but the documentation copy
 * in docs/analytics/ANALYTICS_EXPLAINABILITY.md is still prose, and prose cannot
 * be made to reference a Java constant. So this test reads the document and
 * fails if the two have drifted.
 *
 * Without it, the failure mode is silent: the code discloses one thing, the
 * honesty contract documents another, and nothing complains.
 */
class AnalyticsCaveatContractTest {

    /** docs/ lives two levels above the Maven module directory. */
    private static final Path EXPLAINABILITY_DOC =
            Path.of("..", "..", "docs", "analytics", "ANALYTICS_EXPLAINABILITY.md");

    @Test
    @DisplayName("the caveat states what is estimated and what is not")
    void caveatTextIsMeaningful() {
        String caveat = AnalyticsService.ESTIMATED_SCORE_CAVEAT;

        assertFalse(caveat.isBlank(), "caveat must not be blank");
        assertTrue(caveat.contains("model estimates"),
                "caveat must say the values are model estimates");
        assertTrue(caveat.contains("not figures published by the ranking source"),
                "caveat must say the values are not published figures");
        assertTrue(caveat.contains("never replace a published rank"),
                "caveat must state that estimates do not replace published ranks");
    }

    @Test
    @DisplayName("the explainability doc carries the caveat verbatim")
    void documentationMatchesTheConstant() throws IOException {
        Path doc = EXPLAINABILITY_DOC.toAbsolutePath().normalize();
        assertTrue(Files.isRegularFile(doc),
                "explainability doc not found at " + doc + " -- update this test if docs/ moved");

        String contents = Files.readString(doc, StandardCharsets.UTF_8);
        assertTrue(contents.contains(AnalyticsService.ESTIMATED_SCORE_CAVEAT),
                "docs/analytics/ANALYTICS_EXPLAINABILITY.md no longer contains the exact text of "
                        + "AnalyticsService.ESTIMATED_SCORE_CAVEAT. The honesty contract and the code "
                        + "have drifted -- update the doc, or the constant, so they agree again.");
    }

    /** The literal SNAPSHOT_CAVEAT held before it was rendered from a template. */
    private static final String SNAPSHOT_CAVEAT_2026 =
            "QS ranking data is a point-in-time snapshot of the 2026 published tables. Figures may not reflect rankings republished since this snapshot was ingested.";

    @Test
    @DisplayName("the snapshot caveat for 2026 is the sentence the constant used to hold")
    void snapshotCaveatRendersBackwardIdentically() {
        assertEquals(SNAPSHOT_CAVEAT_2026,
                AnalyticsService.snapshotCaveat(List.of("QS"), List.of(2026)));
        // Over the editions QS was crawled for, not over every edition it covers: the
        // sentence says the data is a snapshot of tables QS published, which is how
        // 2025 and 2026 were obtained. Archive-sourced editions say how they were
        // obtained in their own caveat, so this release-level sentence is unchanged.
        assertEquals(
                AnalyticsService.snapshotCaveat(List.of("QS"), DatasetScope.liveYears("QS")),
                AnalyticsService.SNAPSHOT_CAVEAT);
        assertEquals(List.of(2026, 2025), DatasetScope.liveYears("QS"));
        for (Integer archived : DatasetScope.DATASET_ARCHIVE_EDITIONS.get("QS").keySet()) {
            assertFalse(AnalyticsService.SNAPSHOT_CAVEAT.contains(String.valueOf(archived)));
        }
        assertEquals(AnalyticsService.SNAPSHOT_CAVEAT, AnalyticsService.STANDARD_CAVEATS.get(0));
    }

    @Test
    @DisplayName("a source is never named over an edition it does not cover")
    void aSourceIsNeverNamedOverAnEditionItDoesNotCover() {
        // QS holds no 2015, 2017 or 2021; no source holds 2014.
        assertThrows(IllegalArgumentException.class,
                () -> AnalyticsService.snapshotCaveat(List.of("QS"), List.of(2017)));
        assertThrows(IllegalArgumentException.class,
                () -> AnalyticsService.snapshotCaveat(List.of("QS"), List.of(2015, 2026)));
        assertThrows(IllegalArgumentException.class,
                () -> AnalyticsService.snapshotCaveat(List.of("THE"), List.of(2014)));
        assertTrue(AnalyticsService.editionSnapshotCaveat(2017).startsWith("THE and ARWU ranking data"));
        assertFalse(AnalyticsService.editionSnapshotCaveat(2017).contains("QS"));
    }

    @Test
    @DisplayName("an edition missing a source says so, and one holding them all does not")
    void anEditionDisclosesTheSourcesItLacks() {
        String coverage = AnalyticsService.editionSourceCoverageCaveat(2017);
        assertTrue(coverage.contains("The 2017 edition holds THE and ARWU ranks only"), coverage);
        assertTrue(coverage.contains("No QS rank exists"), coverage);
        // Two of three sources are present, so the sentence must not claim a single one.
        assertFalse(coverage.contains("one source"), coverage);
        assertNull(AnalyticsService.editionSourceCoverageCaveat(2018));
        assertNull(AnalyticsService.editionSourceCoverageCaveat(2026));
    }

    @Test
    @DisplayName("DATASET_YEARS is the union of the per-source coverage map")
    void datasetYearsIsTheUnionOfCoverage() {
        assertTrue(DatasetScope.datasetYearsMatchCoverage(),
                "DatasetScope.DATASET_YEARS and DATASET_COVERAGE disagree about which editions exist");
        assertEquals(List.of("THE", "ARWU"), DatasetScope.sourcesFor(2017));
        assertEquals(List.of("QS", "THE", "ARWU"), DatasetScope.sourcesFor(2018));
        assertEquals(List.of("QS", "THE", "ARWU"), DatasetScope.sourcesFor(2026));
        assertEquals(List.of(), DatasetScope.sourcesFor(2014));
    }

    /** The QS 2023 sentence as Python and TypeScript render it; one golden string in all three suites. */
    private static final String ARCHIVE_CAVEAT_QS_2023 =
            "QS 2023 ranks were recovered from an Internet Archive capture of QS's own data file taken on 2026-05-10, not crawled from QS directly, and QS may have revised the table since. QS prints many ranks as bands (for example 201-210); the rank shown here is the lower bound of the printed rank, so it is not comparable position by position with the QS ranks of 2025 and 2026, which are stored as one position per university. A composite or confidence that includes it inherits that imprecision.";

    @Test
    @DisplayName("an archive-sourced edition says so, and only that edition does")
    void archiveEditionsAreDisclosed() throws IOException {
        assertEquals(ARCHIVE_CAVEAT_QS_2023, AnalyticsService.archiveEditionCaveat("QS", 2023));
        assertNull(AnalyticsService.archiveEditionCaveat("QS", 2026));
        assertNull(AnalyticsService.archiveEditionCaveat("THE", 2024));
        assertFalse(AnalyticsService.archiveEditionCaveat("QS", 2024).contains("{"));

        List<String> shown = AnalyticsService.editionCaveats(2024);
        assertEquals(List.of(
                AnalyticsService.editionSnapshotCaveat(2024),
                AnalyticsService.archiveEditionCaveat("QS", 2024),
                AnalyticsService.THE_PARTIAL_CAVEAT,
                AnalyticsService.ARWU_PARTIAL_CAVEAT), shown);
        for (int year : DatasetScope.DATASET_YEARS) {
            boolean has = AnalyticsService.editionCaveats(year).stream().anyMatch(c -> c.contains("Internet Archive"));
            assertEquals(DatasetScope.archiveCaptureDate("QS", year) != null, has, "edition " + year);
        }
        assertFalse(AnalyticsService.STANDARD_CAVEATS.stream().anyMatch(c -> c.contains("Internet Archive")));

        String contents = Files.readString(EXPLAINABILITY_DOC.toAbsolutePath().normalize(), StandardCharsets.UTF_8);
        assertTrue(contents.contains(AnalyticsService.ARCHIVE_EDITION_CAVEAT_TEMPLATE),
                "the doc no longer carries ARCHIVE_EDITION_CAVEAT_TEMPLATE verbatim");
    }

    @Test
    @DisplayName("year lists render exactly as the explainability doc specifies")
    void editionYearsRenderAsDocumented() throws IOException {
        String contents = Files.readString(EXPLAINABILITY_DOC.toAbsolutePath().normalize(), StandardCharsets.UTF_8);
        assertTrue(contents.contains(AnalyticsService.SNAPSHOT_CAVEAT_TEMPLATE),
                "the doc no longer carries SNAPSHOT_CAVEAT_TEMPLATE verbatim");

        String block = contents
                .split("<!-- year-list-rendering:start -->", 2)[1]
                .split("<!-- year-list-rendering:end -->", 2)[0];
        int checked = 0;
        for (String line : block.strip().split("\\R")) {
            String[] cells = line.strip().replaceAll("^\\||\\|$", "").split("\\|");
            if (cells.length != 2 || !Character.isDigit(cells[0].strip().charAt(0))) {
                continue; // header and separator
            }
            List<Integer> editions = new ArrayList<>();
            for (String year : cells[0].split(",")) {
                editions.add(Integer.parseInt(year.strip()));
            }
            assertEquals(cells[1].strip(), AnalyticsService.formatEditionYears(editions),
                    "rendering of " + editions);
            checked++;
        }
        assertTrue(checked >= 3, "the rendering table lost its rows");
    }

    @Test
    @DisplayName("the caveat is added only when the payload carries an estimate")
    void caveatIsConditional() {
        List<String> withEstimates = new ArrayList<>(List.of("existing caveat"));
        AnalyticsService.appendModelEstimateCaveat(withEstimates, true);
        assertEquals(
                List.of("existing caveat", AnalyticsService.ESTIMATED_SCORE_CAVEAT),
                withEstimates,
                "an estimate-bearing payload must disclose it");

        List<String> withoutEstimates = new ArrayList<>(List.of("existing caveat"));
        AnalyticsService.appendModelEstimateCaveat(withoutEstimates, false);
        assertEquals(
                List.of("existing caveat"),
                withoutEstimates,
                "a payload of published figures must not claim to contain estimates");
    }
}
