package clawer.api;

import clawer.dto.UniversityDTO;
import clawer.service.UniversityService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.Arrays;

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
}
