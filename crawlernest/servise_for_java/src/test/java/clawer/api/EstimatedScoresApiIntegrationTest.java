package clawer.api;

import clawer.service.AnalyticsService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlGroup;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.hasItem;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * The endpoint that surfaces modelled values, and therefore the one place the
 * honesty contract is actually exercised rather than merely defined.
 *
 * What is worth asserting here is not that numbers come back -- it is that they
 * cannot come back undisclosed. Every estimate carries {@code is_estimated} and
 * a support flag, and the response carries
 * {@link AnalyticsService#ESTIMATED_SCORE_CAVEAT}.
 */
@SpringBootTest
@AutoConfigureMockMvc
@SqlGroup({
        @Sql(
                scripts = {
                        "classpath:sql/rankings_integration_setup.sql",
                        "classpath:sql/rankings_integration_seed.sql",
                        "classpath:sql/ml_predictions_integration_setup.sql",
                        "classpath:sql/ml_predictions_integration_seed.sql"
                },
                executionPhase = Sql.ExecutionPhase.BEFORE_TEST_METHOD
        ),
        @Sql(
                scripts = {
                        "classpath:sql/ml_predictions_integration_cleanup.sql",
                        "classpath:sql/rankings_integration_cleanup.sql"
                },
                executionPhase = Sql.ExecutionPhase.AFTER_TEST_METHOD
        )
})
class EstimatedScoresApiIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    @DisplayName("estimates are returned, and every one is disclosed as an estimate")
    void estimatesAreAlwaysDisclosed() throws Exception {
        mockMvc.perform(get("/api/v1/analytics/estimated-scores").accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.metadata.readonly").value(true))
                // The disclosure itself. If this assertion ever has to be relaxed,
                // the honesty contract has been broken, not the test.
                .andExpect(jsonPath("$.metadata.caveats",
                        hasItem(AnalyticsService.ESTIMATED_SCORE_CAVEAT)))
                // Per-item labelling, so a consumer reading one row still knows.
                .andExpect(jsonPath("$.data.items[0].is_estimated").value(true))
                .andExpect(jsonPath("$.data.items[0].is_supported").value(true))
                .andExpect(jsonPath("$.data.model.name").value("ml_predictions_integration_test"));
    }

    @Test
    @DisplayName("unsupported estimates are visible by default and filterable on request")
    void supportFlagIsHonoured() throws Exception {
        // Default: both rows, ordered by estimate descending, unsupported included
        // rather than quietly dropped -- plus the caveat explaining what that means.
        mockMvc.perform(get("/api/v1/analytics/estimated-scores").accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total_count").value(2))
                .andExpect(jsonPath("$.data.items[1].is_supported").value(false))
                .andExpect(jsonPath("$.metadata.caveats", hasItem(
                        "Rows with is_supported = false sit outside the range of data the model was "
                                + "fitted on. Their estimates carry no support from comparable cases.")));

        // supported_only drops the unsupported row.
        mockMvc.perform(get("/api/v1/analytics/estimated-scores")
                        .param("supported_only", "true")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total_count").value(1))
                .andExpect(jsonPath("$.data.items[0].is_supported").value(true))
                .andExpect(jsonPath("$.metadata.caveats",
                        hasItem(AnalyticsService.ESTIMATED_SCORE_CAVEAT)));
    }

    @Test
    @DisplayName("the endpoint stays readonly and never reports a published rank as estimated")
    void estimatesDoNotClaimToBePublishedFigures() throws Exception {
        mockMvc.perform(get("/api/v1/analytics/estimated-scores").accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                // is_estimated is CHECK-constrained true in the schema; assert the
                // API does not invent a false for it on the way out.
                .andExpect(jsonPath("$.data.items[*].is_estimated").value(hasItem(true)))
                .andExpect(jsonPath("$.data.items[*].estimated_overall_score").exists())
                // The field is named estimated_overall_score, never composite_score:
                // the aggregated-rankings vocabulary is reserved for published data.
                .andExpect(jsonPath("$.data.items[0].composite_score").doesNotExist());
    }
}
