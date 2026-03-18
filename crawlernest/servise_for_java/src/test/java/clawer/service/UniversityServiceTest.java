package clawer.service;

import clawer.model.University;
import clawer.repository.UniversityRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;

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
        u1.setName("MIT");
        University u2 = new University();
        u2.setName("Stanford");

        when(universityRepository.findAll()).thenReturn(Arrays.asList(u1, u2));

        List<University> result = universityService.getAllUniversities();

        assertEquals(2, result.size());
        assertEquals("MIT", result.get(0).getName());
        verify(universityRepository, times(1)).findAll();
    }

    @Test
    void testGetUniversityById() {
        University u1 = new University();
        u1.setId("u1");
        u1.setName("MIT");

        when(universityRepository.findById("u1")).thenReturn(Optional.of(u1));

        University result = universityService.getUniversityById("u1");

        assertNotNull(result);
        assertEquals("MIT", result.getName());
    }
}
