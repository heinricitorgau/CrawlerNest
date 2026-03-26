package clawer.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlGroup;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import java.util.HashSet;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@SqlGroup({
        @Sql(
                scripts = {
                        "classpath:sql/rankings_integration_setup.sql",
                        "classpath:sql/rankings_integration_seed.sql"
                },
                executionPhase = Sql.ExecutionPhase.BEFORE_TEST_METHOD
        ),
        @Sql(
                scripts = "classpath:sql/rankings_integration_cleanup.sql",
                executionPhase = Sql.ExecutionPhase.AFTER_TEST_METHOD
        )
})
class RankingApiIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void aggregatedRankingsEndpointReturnsSuccess() throws Exception {
        mockMvc.perform(get("/api/v1/rankings")
                        .param("page", "1")
                        .param("pageSize", "20")
                        .param("source", "AGGREGATED")
                        .param("year", "2099")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.items.length()").value(20))
                .andExpect(jsonPath("$.data.items[0].aggregatedRank").value(1))
                .andExpect(jsonPath("$.data.items[19].aggregatedRank").value(20));
    }

    @Test
    void pageOneIsGloballySortedAndDeterministic() throws Exception {
        JsonNode firstResponse = fetchItems("/api/v1/rankings?page=1&pageSize=20&source=AGGREGATED&year=2099");
        JsonNode secondResponse = fetchItems("/api/v1/rankings?page=1&pageSize=20&source=AGGREGATED&year=2099");

        int previousRank = 0;
        for (int i = 0; i < firstResponse.size(); i++) {
            int currentRank = firstResponse.get(i).get("aggregatedRank").asInt();
            assertTrue(currentRank >= previousRank, "Ranks must be ascending on page 1");
            previousRank = currentRank;

            assertEquals(
                    firstResponse.get(i).get("canonicalUniversityId").asLong(),
                    secondResponse.get(i).get("canonicalUniversityId").asLong(),
                    "Page 1 ordering must be deterministic across repeated calls"
            );
        }
    }

    @Test
    void pageTwoContinuesAfterPageOneWithoutRepeats() throws Exception {
        JsonNode pageOne = fetchItems("/api/v1/rankings?page=1&pageSize=20&source=AGGREGATED&year=2099");
        JsonNode pageTwo = fetchItems("/api/v1/rankings?page=2&pageSize=20&source=AGGREGATED&year=2099");

        assertEquals(20, pageOne.size(), "Page 1 should contain 20 rows");
        assertEquals(5, pageTwo.size(), "Page 2 should contain the remaining 5 rows");

        Set<Long> pageOneIds = new HashSet<>();
        for (JsonNode row : pageOne) {
            pageOneIds.add(row.get("canonicalUniversityId").asLong());
        }

        for (JsonNode row : pageTwo) {
            assertFalse(
                    pageOneIds.contains(row.get("canonicalUniversityId").asLong()),
                    "Page 2 must not repeat rows from page 1"
            );
        }

        int lastRankPageOne = pageOne.get(pageOne.size() - 1).get("aggregatedRank").asInt();
        int firstRankPageTwo = pageTwo.get(0).get("aggregatedRank").asInt();

        assertTrue(firstRankPageTwo >= lastRankPageOne, "Page 2 must continue after page 1");
        assertEquals(lastRankPageOne + 1, firstRankPageTwo, "Fixture should produce contiguous ranks across pages");
    }

    @Test
    void unsupportedSourceReturnsBadRequest() throws Exception {
        mockMvc.perform(get("/api/v1/rankings")
                        .param("source", "QS")
                        .param("year", "2099")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.data.items.length()").value(0))
                .andExpect(jsonPath("$.data.error").value("Only source=AGGREGATED is supported for product rankings."));

        mockMvc.perform(get("/api/v1/rankings")
                        .param("source", "THE")
                        .param("year", "2099")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.data.items.length()").value(0));
    }

    @Test
    void compatibilityRouteOnlyWorksForAggregated() throws Exception {
        mockMvc.perform(get("/api/v1/rankings/AGGREGATED")
                        .param("page", "1")
                        .param("pageSize", "20")
                        .param("year", "2099")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.items.length()").value(20));

        mockMvc.perform(get("/api/v1/rankings/QS")
                        .param("page", "1")
                        .param("pageSize", "20")
                        .param("year", "2099")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false));
    }

    @Test
    void emptyResultForMissingYearKeepsResponseShapeAndDoesNotFallback() throws Exception {
        mockMvc.perform(get("/api/v1/rankings")
                        .param("page", "1")
                        .param("pageSize", "20")
                        .param("source", "AGGREGATED")
                        .param("year", "2098")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.items.length()").value(0));
    }

    private JsonNode fetchItems(String path) throws Exception {
        MvcResult result = mockMvc.perform(get(path).accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andReturn();
        JsonNode root = objectMapper.readTree(result.getResponse().getContentAsString());
        return root.get("data").get("items");
    }
}
