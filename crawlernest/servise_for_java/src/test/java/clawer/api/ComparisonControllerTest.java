package clawer.api;

import clawer.model.UniversityComparisonResult;
import clawer.service.ComparisonService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import clawer.auth.jwt.JwtService;
import clawer.config.SecurityConfig;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

// The real filter chain, not the slice's default one: without it Spring Security's
// fallback closes every path, and these endpoints are public by design. Importing
// it here means a change that accidentally locks them shows up as a failure.
@Import({SecurityConfig.class, JwtService.class})
@WebMvcTest(ComparisonController.class)
class ComparisonControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private ComparisonService comparisonService;

    @Test
    void testCompareReturnsStructuredJson() throws Exception {
        Map<String, Object> ranking = new LinkedHashMap<>();
        ranking.put("winner", "Oxford");
        ranking.put("explanation", "Oxford ranks #3 overall versus LSE at #52, giving it a 49-place aggregated ranking advantage.");

        Map<String, Object> comparison = new LinkedHashMap<>();
        comparison.put("ranking", ranking);

        UniversityComparisonResult result = new UniversityComparisonResult(
                Map.of("canonicalUniversityId", 3L, "universityName", "Oxford"),
                "Oxford ranks #3 overall versus LSE at #52, giving it a 49-place aggregated ranking advantage.",
                List.of("Oxford", "LSE"),
                comparison
        );

        when(comparisonService.compareUniversities(any(), eq(null))).thenReturn(result);

        String jsonPayload = """
                {
                    "leftUniversityId": 3,
                    "rightUniversityId": 52
                }
                """;

        mockMvc.perform(post("/api/v1/compare")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(jsonPayload)
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.data.betterUniversity.universityName").value("Oxford"))
                .andExpect(jsonPath("$.data.comparison.ranking.winner").value("Oxford"));
    }
}
