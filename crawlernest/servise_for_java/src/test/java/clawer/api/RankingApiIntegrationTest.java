package clawer.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
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

    @Autowired
    private JdbcTemplate jdbcTemplate;

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
        assertEquals(9, pageTwo.size(), "Page 2 should contain the remaining rows after page 1");

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
    void pageSizeUsesStrictRowCountEvenWhenRanksContainTies() throws Exception {
        JsonNode pageOne = fetchItems("/api/v1/rankings?page=1&pageSize=25&source=AGGREGATED&year=2099");
        JsonNode pageTwo = fetchItems("/api/v1/rankings?page=2&pageSize=25&source=AGGREGATED&year=2099");

        assertEquals(25, pageOne.size(), "Page 1 should contain exactly 25 rows");
        assertEquals(4, pageTwo.size(), "Page 2 should contain the remaining rows after the first 25");
        assertEquals(25, pageOne.get(pageOne.size() - 1).get("aggregatedRank").asInt());
        assertEquals(26, pageTwo.get(0).get("aggregatedRank").asInt());
        assertEquals(27, pageTwo.get(1).get("aggregatedRank").asInt());
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

    @Test
    void searchForEthReturnsEthZurichAndAvoidsFalsePositives() throws Exception {
        JsonNode items = fetchItems("/api/v1/rankings?page=1&pageSize=20&source=AGGREGATED&year=2099&search=ETH");

        assertTrue(items.size() >= 1, "ETH search should return at least one result");
        assertEquals("ETH Zurich", items.get(0).get("universityName").asText());

        for (JsonNode item : items) {
            assertFalse(
                    "Delft University of Technology".equals(item.get("universityName").asText()),
                    "Short token search should not match unrelated Technology substrings"
            );
            assertFalse(
                    "Netherlands".equals(item.path("country").asText()),
                    "Search must not match by country name"
            );
        }
    }

    @Test
    void longerSearchCanStillReturnRelevantTechnologyMatches() throws Exception {
        JsonNode items = fetchItems("/api/v1/rankings?page=1&pageSize=20&source=AGGREGATED&year=2099&search=technology");

        assertTrue(items.size() >= 2, "Longer search should still return relevant technology universities");
        assertEquals("Massachusetts Institute of Technology", items.get(0).get("universityName").asText());
        assertEquals("Delft University of Technology", items.get(1).get("universityName").asText());
    }

    @Test
    void countrySearchMatchesCountryWithoutOverridingNamePriority() throws Exception {
        JsonNode items = fetchItems("/api/v1/rankings?page=1&pageSize=20&source=AGGREGATED&year=2099&search=Netherlands");

        assertEquals(1, items.size(), "Country search should return the matching university rows in this fixture");
        assertEquals("Delft University of Technology", items.get(0).get("universityName").asText());
        assertEquals("Netherlands", items.get(0).get("country").asText());
    }

    @Test
    void countrySearchReturnsUnitedKingdomUniversities() throws Exception {
        MvcResult result = mockMvc.perform(get("/api/v1/rankings")
                        .param("page", "1")
                        .param("pageSize", "20")
                        .param("source", "AGGREGATED")
                        .param("year", "2099")
                        .param("search", "United Kingdom")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andReturn();
        JsonNode items = objectMapper.readTree(result.getResponse().getContentAsString()).get("data").get("items");

        assertTrue(items.size() >= 1, "United Kingdom country search should return at least one result");
        assertEquals("University of Oxford", items.get(0).get("universityName").asText());
        assertEquals("United Kingdom", items.get(0).get("country").asText());
    }

    @Test
    void regionScopeReRanksWithinRegionAndPreservesGlobalRank() throws Exception {
        JsonNode items = fetchItems(
                "/api/v1/rankings?page=1&pageSize=20&source=AGGREGATED&year=2099&scope=region&region=Europe"
        );

        assertEquals(4, items.size(), "Europe fixture should return the full Europe aggregation universe");
        assertEquals("ETH Zurich", items.get(0).get("universityName").asText());
        assertEquals(1, items.get(0).get("globalRank").asInt());
        assertEquals(1, items.get(0).get("scopeRank").asInt());
        assertEquals(1, items.get(0).get("aggregatedRank").asInt());

        assertEquals("Delft University of Technology", items.get(1).get("universityName").asText());
        assertEquals(3, items.get(1).get("globalRank").asInt());
        assertEquals(2, items.get(1).get("scopeRank").asInt());
        assertEquals(2, items.get(1).get("aggregatedRank").asInt());

        assertEquals("University of Oxford", items.get(2).get("universityName").asText());
        assertEquals(28, items.get(2).get("globalRank").asInt());
        assertEquals(3, items.get(2).get("scopeRank").asInt());
        assertEquals(3, items.get(2).get("aggregatedRank").asInt());

        assertEquals("University of Barcelona", items.get(3).get("universityName").asText());
        assertEquals(29, items.get(3).get("globalRank").asInt());
        assertEquals(4, items.get(3).get("scopeRank").asInt());
        assertEquals(4, items.get(3).get("aggregatedRank").asInt());
    }

    @Test
    void regionAggregationIncludesCoverageBeyondGlobalTopSlice() throws Exception {
        JsonNode globalTopSlice = fetchItems("/api/v1/rankings?page=1&pageSize=20&source=AGGREGATED&year=2099");
        JsonNode europe = fetchItems(
                "/api/v1/rankings?page=1&pageSize=20&source=AGGREGATED&year=2099&scope=region&region=Europe"
        );

        Set<String> globalNames = new HashSet<>();
        for (JsonNode item : globalTopSlice) {
            globalNames.add(item.get("universityName").asText());
        }

        assertFalse(globalNames.contains("University of Barcelona"), "Global top slice should not contain the Barcelona fixture row");
        assertTrue(
                containsUniversity(europe, "University of Barcelona"),
                "Europe aggregation should include universities outside the current global top slice"
        );
        assertTrue(
                containsCountry(europe, "Spain"),
                "Europe aggregation should widen regional country coverage"
        );
    }

    @Test
    void regionAggregationRanksAreContiguousWithoutNulls() throws Exception {
        JsonNode europe = fetchItems(
                "/api/v1/rankings?page=1&pageSize=20&source=AGGREGATED&year=2099&scope=region&region=Europe"
        );

        assertEquals(4, europe.size());
        for (int i = 0; i < europe.size(); i++) {
            assertEquals(i + 1, europe.get(i).get("scopeRank").asInt());
            assertFalse(europe.get(i).get("scopeRank").isNull());
        }
    }

    @Test
    void latestUniverseViewAndRegionReadPathDoNotExplodeRowsWhenOlderMethodsExist() throws Exception {
        jdbcTemplate.update("""
                INSERT INTO analytics.aggregation_runs (
                    aggregation_run_id,
                    run_label,
                    ranking_year,
                    universe_type,
                    universe_key,
                    aggregation_method_version,
                    status,
                    input_record_count,
                    output_record_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                990099L,
                "ranking_api_integration_test_global_v2",
                2099,
                "global",
                "global",
                "rank_agg_test_v2",
                "finished",
                29,
                29
        );

        jdbcTemplate.update("""
                INSERT INTO analytics.aggregated_rankings (
                    aggregation_run_id,
                    canonical_university_id,
                    ranking_year,
                    universe_type,
                    universe_key,
                    display_rank,
                    composite_score,
                    coverage_ratio,
                    source_ranks_json,
                    source_normalized_scores_json,
                    source_weights_used_json,
                    aggregation_method_version
                )
                SELECT
                    ?,
                    canonical_university_id,
                    ranking_year,
                    universe_type,
                    universe_key,
                    display_rank,
                    composite_score,
                    coverage_ratio,
                    source_ranks_json,
                    source_normalized_scores_json,
                    source_weights_used_json,
                    ?
                FROM analytics.aggregated_rankings
                WHERE aggregation_run_id = ?
                  AND universe_type = 'global'
                  AND universe_key = 'global'
                """,
                990099L,
                "rank_agg_test_v2",
                990001L
        );

        Integer europeCount = jdbcTemplate.queryForObject("""
                SELECT COUNT(*)
                FROM analytics.v_aggregated_rankings_latest
                WHERE ranking_year = 2099
                  AND universe_type = 'region'
                  AND universe_key = 'europe'
                """, Integer.class);
        Integer europeDistinct = jdbcTemplate.queryForObject("""
                SELECT COUNT(DISTINCT canonical_university_id)
                FROM analytics.v_aggregated_rankings_latest
                WHERE ranking_year = 2099
                  AND universe_type = 'region'
                  AND universe_key = 'europe'
                """, Integer.class);

        assertEquals(4, europeCount);
        assertEquals(4, europeDistinct);

        JsonNode europe = fetchItems(
                "/api/v1/rankings?page=1&pageSize=20&source=AGGREGATED&year=2099&scope=region&region=Europe"
        );

        assertEquals(4, europe.size());
        Set<Long> seenIds = new HashSet<>();
        for (int i = 0; i < europe.size(); i++) {
            JsonNode item = europe.get(i);
            long canonicalId = item.get("canonicalUniversityId").asLong();
            assertTrue(seenIds.add(canonicalId), "Europe response must not repeat canonical universities");
            assertEquals(i + 1, item.get("scopeRank").asInt(), "Scope ranks must stay contiguous");
        }
    }

    @Test
    void regionScopeSearchRespectsRegionUniverseBeforePagination() throws Exception {
        JsonNode items = fetchItems(
                "/api/v1/rankings?page=1&pageSize=20&source=AGGREGATED&year=2099&scope=region&region=Europe&search=Netherlands"
        );

        assertEquals(1, items.size(), "Region-scoped search should only return matches inside the active region universe");
        assertEquals("Delft University of Technology", items.get(0).get("universityName").asText());
        assertEquals(2, items.get(0).get("scopeRank").asInt());
        assertEquals(3, items.get(0).get("globalRank").asInt());
    }

    @Test
    void regionScopeCountrySearchReturnsUnitedKingdomUniversities() throws Exception {
        MvcResult result = mockMvc.perform(get("/api/v1/rankings")
                        .param("page", "1")
                        .param("pageSize", "20")
                        .param("source", "AGGREGATED")
                        .param("year", "2099")
                        .param("scope", "region")
                        .param("region", "Europe")
                        .param("search", "United Kingdom")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andReturn();
        JsonNode items = objectMapper.readTree(result.getResponse().getContentAsString()).get("data").get("items");

        assertTrue(items.size() >= 1, "Region-scoped country search should return UK universities inside Europe");
        assertEquals("University of Oxford", items.get(0).get("universityName").asText());
        assertEquals("United Kingdom", items.get(0).get("country").asText());
        assertEquals(3, items.get(0).get("scopeRank").asInt());
    }

    @Test
    void latestUniverseViewDeduplicatesCanonicalRowsInsideLatestRunAndKeepsRanksTrustworthy() throws Exception {
        jdbcTemplate.update("""
                INSERT INTO analytics.aggregated_rankings (
                    aggregation_run_id,
                    canonical_university_id,
                    ranking_year,
                    universe_type,
                    universe_key,
                    display_rank,
                    composite_score,
                    coverage_ratio,
                    source_ranks_json,
                    source_normalized_scores_json,
                    source_weights_used_json,
                    aggregation_method_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?::jsonb, ?::jsonb, ?::jsonb, ?)
                """,
                990002L,
                990003L,
                2099,
                "region",
                "europe",
                99,
                0.100000,
                1.0,
                "{\"QS\":999}",
                "{\"QS\":0.1}",
                "{\"QS\":1.0}",
                "rank_agg_shadow_v9"
        );

        Integer europeCount = jdbcTemplate.queryForObject("""
                SELECT COUNT(*)
                FROM analytics.v_aggregated_rankings_latest
                WHERE ranking_year = 2099
                  AND universe_type = 'region'
                  AND universe_key = 'europe'
                """, Integer.class);
        Integer europeDistinct = jdbcTemplate.queryForObject("""
                SELECT COUNT(DISTINCT canonical_university_id)
                FROM analytics.v_aggregated_rankings_latest
                WHERE ranking_year = 2099
                  AND universe_type = 'region'
                  AND universe_key = 'europe'
                """, Integer.class);

        assertEquals(4, europeCount);
        assertEquals(4, europeDistinct);

        JsonNode europe = fetchItems(
                "/api/v1/rankings?page=1&pageSize=20&source=AGGREGATED&year=2099&scope=region&region=Europe"
        );

        assertEquals(4, europe.size());
        assertEquals("ETH Zurich", europe.get(0).get("universityName").asText());
        assertEquals(1, europe.get(0).get("scopeRank").asInt());
        assertEquals("Delft University of Technology", europe.get(1).get("universityName").asText());
        assertEquals(2, europe.get(1).get("scopeRank").asInt());
        assertEquals("University of Oxford", europe.get(2).get("universityName").asText());
        assertEquals(3, europe.get(2).get("scopeRank").asInt());
        assertEquals("University of Barcelona", europe.get(3).get("universityName").asText());
        assertEquals(4, europe.get(3).get("scopeRank").asInt());
    }

    @Test
    void regionScopeRequiresValidRegion() throws Exception {
        mockMvc.perform(get("/api/v1/rankings")
                        .param("scope", "region")
                        .param("year", "2099")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.data.error").value("region is required when scope=region."));

        mockMvc.perform(get("/api/v1/rankings")
                        .param("scope", "region")
                        .param("region", "Atlantis")
                        .param("year", "2099")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.data.error").value("Unsupported region. Supported values: Europe, Asia, North America, Latin America, Oceania, Africa."));
    }

    private JsonNode fetchItems(String path) throws Exception {
        MvcResult result = mockMvc.perform(get(path).accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andReturn();
        JsonNode root = objectMapper.readTree(result.getResponse().getContentAsString());
        return root.get("data").get("items");
    }

    private boolean containsUniversity(JsonNode items, String universityName) {
        for (JsonNode item : items) {
            if (universityName.equals(item.get("universityName").asText())) {
                return true;
            }
        }
        return false;
    }

    private boolean containsCountry(JsonNode items, String countryName) {
        for (JsonNode item : items) {
            if (countryName.equals(item.get("country").asText())) {
                return true;
            }
        }
        return false;
    }
}
