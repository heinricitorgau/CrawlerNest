package clawer.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlGroup;
import org.springframework.test.web.servlet.MockMvc;

import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * The ranking-trends endpoint with two held editions and a merger between them.
 *
 * <p>Before this, the endpoint subtracted one edition's composite display_rank
 * from the other's for every university -- a number that mostly measures source
 * coverage, and that across a merger compares two different institutions. It now
 * reports no delta at all and says per row why.
 */
@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(properties = "crawlernest.dataset.years=2099,2100")
@SqlGroup({
        @Sql(
                scripts = {
                        "classpath:sql/rankings_integration_setup.sql",
                        "classpath:sql/rankings_integration_seed.sql",
                        "classpath:sql/rankings_integration_edition_2100.sql",
                        "classpath:sql/institution_lineage_integration_setup.sql"
                },
                executionPhase = Sql.ExecutionPhase.BEFORE_TEST_METHOD
        ),
        @Sql(
                scripts = {
                        "classpath:sql/institution_lineage_integration_cleanup.sql",
                        "classpath:sql/rankings_integration_cleanup.sql"
                },
                executionPhase = Sql.ExecutionPhase.AFTER_TEST_METHOD
        )
})
class RankingTrendsLineageIntegrationTest {

    private static final long ETH_ZURICH = 990001L;
    private static final long MIT = 990002L;

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void noRowCarriesADeltaAndTheMergedPairSaysWhy() throws Exception {
        String body = mockMvc.perform(get("/api/v1/analytics/ranking-trends").accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString();
        JsonNode data = objectMapper.readTree(body).get("data");

        assertEquals(2100, data.get("available_years").get(0).asInt());
        assertEquals(2099, data.get("available_years").get(1).asInt());
        assertEquals(false, data.get("single_year_only").asBoolean());

        Map<Long, JsonNode> fixtureRows = new HashMap<>();
        for (JsonNode item : data.get("items")) {
            long id = item.get("canonical_university_id").asLong();
            assertTrue(item.get("rank_delta") == null || item.get("rank_delta").isNull(),
                    "a composite delta was computed for " + id);
            if (id >= 990001L && id <= 990030L) {
                assertTrue(fixtureRows.put(id, item) == null,
                        "university " + id + " appears twice; the prior edition was joined without its year");
            }
        }
        assertEquals(29, fixtureRows.size());

        for (long merged : new long[]{ETH_ZURICH, MIT}) {
            JsonNode row = fixtureRows.get(merged);
            assertEquals("entity_changed", row.get("rank_delta_reason").asText(), "row " + merged);
            assertTrue(row.get("previous_rank").isNull(),
                    "the prior edition's rank belongs to a different institution: " + row);
        }

        JsonNode unrelated = fixtureRows.get(990003L);
        assertEquals("composite_rank_not_comparable", unrelated.get("rank_delta_reason").asText());
        assertEquals(2099, unrelated.get("previous_year").asInt());
        assertEquals(3, unrelated.get("previous_rank").asInt());
    }
}
