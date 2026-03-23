package clawer.service;

import clawer.dto.UniversityDTO;
import clawer.model.University;
import clawer.repository.UniversityRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;

import java.util.Arrays;
import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class UniversityServiceTest {

    @Mock
    private UniversityRepository universityRepository;

    @InjectMocks
    private UniversityService universityService;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
    }

    @Test
    void testGetAllUniversities() {
        University u1 = new University();
        u1.setId(1L);
        u1.setDisplayName("MIT");
        University u2 = new University();
        u2.setId(2L);
        u2.setDisplayName("Stanford");

        when(universityRepository.findAll(PageRequest.of(0, 20))).thenReturn(new PageImpl<>(Arrays.asList(u1, u2)));

        List<UniversityDTO> result = universityService.getAllUniversities(0, 20);

        assertEquals(2, result.size());
        assertEquals("MIT", result.get(0).getDisplayName());
        verify(universityRepository, times(1)).findAll(PageRequest.of(0, 20));
    }

    @Test
    void testGetUniversityById() {
        University u1 = new University();
        u1.setId(1L);
        u1.setDisplayName("MIT");

        when(universityRepository.findById(1L)).thenReturn(Optional.of(u1));

        UniversityDTO result = universityService.getUniversityById(1L);

        assertNotNull(result);
        assertEquals("MIT", result.getDisplayName());
    }
}
