package clawer.api;

import clawer.dto.AdmissionRequirementDTO;
import clawer.dto.AdmissionRequirementsDTO;
import clawer.dto.UniversityDTO;
import clawer.service.SourceIntelligenceService;
import clawer.service.UniversityService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Arrays;
import java.util.List;

import static org.hamcrest.Matchers.nullValue;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Slice test for UniversityController.
 * This tests ONLY the web layer (Controller), including mapping and serialization.
 */
@WebMvcTest(UniversityController.class)
class UniversityControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private UniversityService universityService;

    @MockBean
    private SourceIntelligenceService sourceIntelligenceService;

    @Test
    void testGetAllUniversities_ReturnsJsonList() throws Exception {
        UniversityDTO u1 = new UniversityDTO();
        u1.setCanonicalUniversityId(1L);
        u1.setUniversityName("Test Uni");
        
        when(universityService.getAllUniversities(anyInt(), anyInt())).thenReturn(Arrays.asList(u1));

        mockMvc.perform(get("/api/v1/universities")
                .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.data[0].universityName").value("Test Uni"))
                .andExpect(jsonPath("$.data[0].canonicalUniversityId").value(1));
    }

    @Test
    void testGetUniversityById_NotFound_Returns404() throws Exception {
        when(universityService.getUniversityById(anyLong())).thenReturn(null);

        mockMvc.perform(get("/api/v1/universities/999"))
                .andExpect(status().isNotFound());
    }

    @Test
    void testAdmissionRequirementsSerializeWithNullsIntact() throws Exception {
        AdmissionRequirementDTO postgraduate = new AdmissionRequirementDTO();
        postgraduate.setDegreeLevel("postgraduate");
        postgraduate.setIeltsRequirement(7.0);
        postgraduate.setToeflRequirement(100);
        postgraduate.setApplicationDeadline("2026-01-15");

        AdmissionRequirementsDTO admissions = new AdmissionRequirementsDTO();
        admissions.setHasData(true);
        admissions.setDegreeLevelCount(1);
        admissions.setByDegreeLevel(List.of(postgraduate));
        admissions.setSummary(postgraduate);

        UniversityDTO dto = new UniversityDTO();
        dto.setCanonicalUniversityId(1L);
        dto.setUniversityName("Test Uni");
        dto.setAdmissionRequirements(admissions);

        when(universityService.getUniversityById(anyLong())).thenReturn(dto);

        mockMvc.perform(get("/api/v1/universities/1").accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.admissionRequirements.hasData").value(true))
                .andExpect(jsonPath("$.data.admissionRequirements.degreeLevelCount").value(1))
                .andExpect(jsonPath("$.data.admissionRequirements.summary.ieltsRequirement").value(7.0))
                .andExpect(jsonPath("$.data.admissionRequirements.summary.toeflRequirement").value(100))
                .andExpect(jsonPath("$.data.admissionRequirements.summary.applicationDeadline").value("2026-01-15"))
                // A requirement the source never published must reach the client as
                // an explicit JSON null. value(nullValue()) rather than doesNotExist(),
                // which passes for a present-but-null key as well and so would prove
                // nothing about which of the two the client actually receives.
                .andExpect(jsonPath("$.data.admissionRequirements.summary.gpaRequirement").value(nullValue()))
                .andExpect(jsonPath("$.data.admissionRequirements.summary.duolingoRequirement").value(nullValue()))
                .andExpect(jsonPath("$.data.admissionRequirements.byDegreeLevel[0].degreeLevel").value("postgraduate"));
    }

    @Test
    void testAdmissionRequirementsEmptyStateIsAnObjectNotNull() throws Exception {
        UniversityDTO dto = new UniversityDTO();
        dto.setCanonicalUniversityId(2L);
        dto.setUniversityName("No Admissions Uni");
        dto.setAdmissionRequirements(AdmissionRequirementsDTO.empty());

        when(universityService.getUniversityById(anyLong())).thenReturn(dto);

        mockMvc.perform(get("/api/v1/universities/2").accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.admissionRequirements.hasData").value(false))
                .andExpect(jsonPath("$.data.admissionRequirements.degreeLevelCount").value(0))
                .andExpect(jsonPath("$.data.admissionRequirements.byDegreeLevel").isArray())
                .andExpect(jsonPath("$.data.admissionRequirements.byDegreeLevel").isEmpty())
                .andExpect(jsonPath("$.data.admissionRequirements.summary").exists())
                .andExpect(jsonPath("$.data.admissionRequirements.summary.ieltsRequirement").value(nullValue()));
    }
}
