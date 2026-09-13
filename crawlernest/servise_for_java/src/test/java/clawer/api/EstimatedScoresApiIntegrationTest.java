package clawer.api;

import clawer.service.AnalyticsService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlGroup;
import org.springframework.test.web.servlet.MockMvc;

import static org.hamcrest.Matchers.hasItem;
import static org.hamcrest.Matchers.not;
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
// The fixture estimates are for edition 2099; estimates are read for the held edition only.
@TestPropertySource(properties = "crawlernest.dataset.years=2099")
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
    @DisplayName("each endpoint returns only its own target")
    void targetsDoNotLeakBetweenEndpoints() throws Exception {
        // The view holds the latest run per target, so both fixtures are visible
        // to an unfiltered query. Without a target filter, estimated-scores would
        // return three rows instead of two and disagreement-risk would lead with
        // a 42.5 "probability".
        mockMvc.perform(get("/api/v1/analytics/estimated-scores").accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total_count").value(2))
                .andExpect(jsonPath("$.data.model.name").value("ml_predictions_integration_test"))
                // a probability would sort last here and be quietly appended
                .andExpect(jsonPath("$.data.items[*].estimated_overall_score",
                        not(hasItem(0.96))));

        mockMvc.perform(get("/api/v1/analytics/disagreement-risk").accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.total_count").value(1))
                .andExpect(jsonPath("$.data.model.name").value("ml_disagreement_integration_test"))
                .andExpect(jsonPath("$.data.items[0].disagreement_probability").value(0.96))
                // the score endpoint's field name must not appear here
                .andExpect(jsonPath("$.data.items[0].estimated_overall_score").doesNotExist());
    }

    @Test
    @DisplayName("a disagreement probability is disclosed as an estimate and as a probability")
    void disagreementRiskIsDisclosed() throws Exception {
        mockMvc.perform(get("/api/v1/analytics/disagreement-risk").accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.metadata.readonly").value(true))
                .andExpect(jsonPath("$.metadata.caveats",
                        hasItem(AnalyticsService.ESTIMATED_SCORE_CAVEAT)))
                // The distinction that keeps this honest: a probability is not a
                // finding about the university.
                .andExpect(jsonPath("$.metadata.caveats", hasItem(
                        "This is a probability, not a finding. A high value means universities with "
                                + "similar QS profiles are often placed differently by THE, not that this "
                                + "university has been shown to be misranked.")))
                .andExpect(jsonPath("$.data.items[0].is_estimated").value(true))
                .andExpect(jsonPath("$.data.items[0].is_supported").value(true));
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
