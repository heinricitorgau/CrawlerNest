package clawer.service;

import clawer.dto.UniversityDTO;
import clawer.model.University;
import clawer.repository.UniversityRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;

import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class UniversityServiceTest {

    @Mock
    private UniversityRepository universityRepository;

    @Mock
    private JdbcTemplate jdbcTemplate;

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
        assertEquals("MIT", result.get(0).getUniversityName());
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
        assertEquals("MIT", result.getUniversityName());
    }

    @Test
    @SuppressWarnings("unchecked")
    void testGetUniversityBySlug_UsesCanonicalEvidenceAcrossSources() {
        University legacy = new University();
        legacy.setId(10L);
        legacy.setSchoolSlug("mit");
        legacy.setDisplayName("MIT");

        when(universityRepository.findBySchoolSlug("mit")).thenReturn(Optional.of(legacy));
        when(jdbcTemplate.query(
                contains("FROM warehouse.canonical_university_link cul"),
                any(Object[].class),
                any(RowMapper.class)
        )).thenReturn(List.of(9001L));
        when(jdbcTemplate.query(
                contains("FROM analytics.v_aggregated_rankings_latest"),
                any(Object[].class),
                any(RowMapper.class)
        )).thenReturn(List.of(Map.of(
                "ranking_year", 2026,
                "display_rank", 2,
                "composite_score", 98.1,
                "aggregation_method_version", "v2"
        )));
        when(jdbcTemplate.query(
                contains("WITH ranked_source_rows AS"),
                any(Object[].class),
                any(RowMapper.class)
        )).thenReturn(List.of(
                Map.of("source_code", "QS", "ranking_year", 2026, "rank_position", 1, "score", 100.0),
                Map.of("source_code", "THE", "ranking_year", 2026, "rank_position", 2, "score", 99.0),
                Map.of("source_code", "ARWU", "ranking_year", 2026, "rank_position", 3, "score", 98.0)
        ));

        UniversityDTO result = universityService.getUniversityBySlug("mit");

        assertNotNull(result);
        assertEquals(9001L, result.getCanonicalUniversityId());
        assertEquals(3, result.getSourceRankings().size());
        assertEquals(List.of("QS", "THE", "ARWU"), result.getSourceRankings().stream().map(r -> r.getSource()).toList());
        assertEquals(3, result.getRankingEvidence().size());
    }
}
