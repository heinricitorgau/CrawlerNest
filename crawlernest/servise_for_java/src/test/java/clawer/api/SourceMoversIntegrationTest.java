package clawer.api;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import clawer.service.AnalyticsService;

import static org.hamcrest.Matchers.hasItem;
import static org.hamcrest.Matchers.lessThan;
import static org.hamcrest.Matchers.greaterThan;
import static org.hamcrest.Matchers.everyItem;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * GET /api/v1/analytics/source-movers: exact movements only, an edition the source lacks is withheld and said so,
 * and the rank-change caveat is always present. Shape and rules only; the counts depend on the warehouse.
 */
@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(properties = "crawlernest.jwt.secret=an-integration-test-secret-long-enough-for-hs256")
class SourceMoversIntegrationTest {

    @Autowired
    private MockMvc mvc;

    @Test
    void anEditionTheSourceDoesNotHoldIsWithheldNotReachedAround() throws Exception {
        // QS holds no 2016: 2017 is withheld rather than compared with anything older.
        mvc.perform(get("/api/v1/analytics/source-movers").param("source", "qs").param("year", "2017"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.source").value("QS"))
                .andExpect(jsonPath("$.data.prior_year").value(2016))
                .andExpect(jsonPath("$.data.withheld_reason").value("no_qs_edition_2016"))
                .andExpect(jsonPath("$.data.risers").isEmpty())
                .andExpect(jsonPath("$.data.caveats", hasItem(AnalyticsService.RANK_CHANGE_CAVEAT)));
    }

    @Test
    void risersImproveAndFallersDecline() throws Exception {
        mvc.perform(get("/api/v1/analytics/source-movers").param("source", "THE").param("year", "2026").param("limit", "5"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.prior_year").value(2025))
                .andExpect(jsonPath("$.data.risers[*].rankDelta", everyItem(lessThan(0))))
                .andExpect(jsonPath("$.data.fallers[*].rankDelta", everyItem(greaterThan(0))))
                .andExpect(jsonPath("$.data.caveats", hasItem(AnalyticsService.RANK_CHANGE_CAVEAT)));
    }

    @Test
    void anUnknownSourceOrUnheldYearIsABadRequest() throws Exception {
        mvc.perform(get("/api/v1/analytics/source-movers").param("source", "USNEWS")).andExpect(status().isBadRequest());
        mvc.perform(get("/api/v1/analytics/source-movers").param("source", "THE").param("year", "1999"))
                .andExpect(status().isBadRequest());
    }
}
