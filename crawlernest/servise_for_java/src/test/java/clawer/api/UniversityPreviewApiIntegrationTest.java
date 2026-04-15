package clawer.api;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlGroup;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@SqlGroup({
        @Sql(
                scripts = {
                        "classpath:sql/university_preview_integration_setup.sql",
                        "classpath:sql/university_preview_integration_seed.sql"
                },
                executionPhase = Sql.ExecutionPhase.BEFORE_TEST_METHOD
        ),
        @Sql(
                scripts = "classpath:sql/university_preview_integration_cleanup.sql",
                executionPhase = Sql.ExecutionPhase.AFTER_TEST_METHOD
        )
})
class UniversityPreviewApiIntegrationTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void canonicalUniversityIdLookupReturnsMitPreview() throws Exception {
        mockMvc.perform(get("/api/v1/preview/universities")
                        .param("canonicalUniversityId", "990102")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.canonicalUniversityId").value(990102))
                .andExpect(jsonPath("$.data.universityDisplayName").value("Massachusetts Institute of Technology"))
                .andExpect(jsonPath("$.data.aliases[0]").value("MIT"))
                .andExpect(jsonPath("$.data.rankingSummary").exists())
                .andExpect(jsonPath("$.data.admissionSummary").exists())
                .andExpect(jsonPath("$.data.dataAvailability.hasRankingData").value(true))
                .andExpect(jsonPath("$.data.dataAvailability.hasAdmissionData").value(true))
                .andExpect(jsonPath("$.data.dataAvailability.missingSections.length()").value(0));
    }

    @Test
    void universityNameLookupReturnsMitPreview() throws Exception {
        mockMvc.perform(get("/api/v1/preview/universities")
                        .param("universityName", "Massachusetts Institute of Technology")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.canonicalUniversityId").value(990102))
                .andExpect(jsonPath("$.data.identitySummary.matchedBy").value("displayNameNormalized"))
                .andExpect(jsonPath("$.data.rankingSummary.bestSource").value("QS"))
                .andExpect(jsonPath("$.data.admissionSummary.bestIeltsRequirement").value(7.0))
                .andExpect(jsonPath("$.data.admissionSummary.bestToeflRequirement").value(100));
    }

    @Test
    void missingQueryParametersReturnBadRequest() throws Exception {
        mockMvc.perform(get("/api/v1/preview/universities")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.data.error").value("canonicalUniversityId or universityName is required."));
    }

    @Test
    void unknownUniversityReturnsNotFound() throws Exception {
        mockMvc.perform(get("/api/v1/preview/universities")
                        .param("universityName", "Unknown Preview University")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.data.error").value("University preview not found."));
    }
}
