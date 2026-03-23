package clawer.api;

import clawer.model.UniversityComparisonResult;
import clawer.service.ComparisonService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

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
                "Oxford",
                "Oxford ranks #3 overall versus LSE at #52, giving it a 49-place aggregated ranking advantage.",
                List.of("Oxford", "LSE"),
                comparison
        );

        when(comparisonService.compareUniversities(any(), eq(null))).thenReturn(result);

        mockMvc.perform(get("/compare")
                        .param("u1", "Oxford")
                        .param("u2", "LSE")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.better").value("Oxford"))
                .andExpect(jsonPath("$.comparison.ranking.winner").value("Oxford"));
    }
}
