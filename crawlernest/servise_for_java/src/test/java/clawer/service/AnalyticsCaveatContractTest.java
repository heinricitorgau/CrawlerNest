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
