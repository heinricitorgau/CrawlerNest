package clawer.service;

import clawer.dto.AdmissionRequirementDTO;
import clawer.dto.AdmissionRequirementsDTO;
import clawer.dto.UniversityDTO;
import clawer.model.University;
import clawer.repository.AdmissionRecordRepository;
import clawer.repository.UniversityRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.mockito.Spy;
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
    private AdmissionRecordRepository admissionRecordRepository;

    @Mock
    private JdbcTemplate jdbcTemplate;

    @Mock
    private clawer.repository.InstitutionLineageRepository institutionLineageRepository;

    /** A real scope: the aggregated-ranking read now names the release's default edition. */
    @Spy
    private DatasetScope datasetScope = DatasetScope.standard();

    @InjectMocks
    private UniversityService universityService;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
        // Most universities have no crawled admission page, so the no-data shape
        // is the default here rather than the exception.
        lenient().when(admissionRecordRepository.findByCanonicalUniversityId(any()))
                .thenReturn(AdmissionRequirementsDTO.empty());
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
        // The source-rank query answers for the edition it is asked for, as the
        // SQL does: 2026 rows for 2026, 2025 rows for 2025.
        when(jdbcTemplate.query(
                contains("WITH ranked_source_rows AS"),
                any(Object[].class),
                any(RowMapper.class)
        )).thenAnswer(invocation -> {
            int year = (Integer) ((Object[]) invocation.getArgument(1))[1];
            if (year == 2026) {
                return List.of(
                        sourceRow("QS", 2026, 1, "1", "/universities/mit"),
                        sourceRow("THE", 2026, 2, "2", "the:mit"),
                        sourceRow("ARWU", 2026, 3, "3", "arwu:mit"));
            }
            if (year == 2025) {
                return List.of(
                        sourceRow("QS", 2025, 1, "1", "/universities/mit"),
                        sourceRow("THE", 2025, 201, "201–250", "the:mit"));
            }
            return List.of();
        });

        UniversityDTO result = universityService.getUniversityBySlug("mit");

        assertNotNull(result);
        assertEquals(9001L, result.getCanonicalUniversityId());
        assertEquals(3, result.getSourceRankings().size());
        assertEquals(List.of("QS", "THE", "ARWU"), result.getSourceRankings().stream().map(r -> r.getSource()).toList());
        assertEquals(3, result.getRankingEvidence().size());
    }

    private static Map<String, Object> sourceRow(String source, int year, int position, String display, String entityId) {
        Map<String, Object> row = new java.util.HashMap<>();
        row.put("source_code", source);
        row.put("ranking_year", year);
        row.put("rank_position", position);
        row.put("score", 90.0);
        row.put("rank_display", display);
        row.put("source_entity_id", entityId);
        row.put("suspicious_merge", false);
        return row;
    }

    @Test
    @SuppressWarnings("unchecked")
    void sourceRankingsCarryAPerSourceDeltaFromThePriorHeldEdition() {
        DatasetScope twoEditions = new DatasetScope("2026,2025");
        UniversityService service = new UniversityService(
                universityRepository, admissionRecordRepository, jdbcTemplate, twoEditions, institutionLineageRepository);
        University legacy = new University();
        legacy.setId(10L);
        legacy.setSchoolSlug("mit");
        when(universityRepository.findBySchoolSlug("mit")).thenReturn(Optional.of(legacy));
        when(institutionLineageRepository.findInvolving(any())).thenReturn(List.of());
        when(jdbcTemplate.query(contains("FROM warehouse.canonical_university_link cul"), any(Object[].class), any(RowMapper.class)))
                .thenReturn(List.of(9001L));
        when(jdbcTemplate.query(contains("FROM analytics.v_aggregated_rankings_latest"), any(Object[].class), any(RowMapper.class)))
                .thenReturn(List.of(Map.of("ranking_year", 2026, "display_rank", 2, "composite_score", 98.1,
                        "aggregation_method_version", "v2")));
        when(jdbcTemplate.query(contains("WITH ranked_source_rows AS"), any(Object[].class), any(RowMapper.class)))
                .thenAnswer(invocation -> {
                    int year = (Integer) ((Object[]) invocation.getArgument(1))[1];
                    return year == 2026
                            ? List.of(sourceRow("QS", 2026, 14, "14", "/universities/x"),
                                      sourceRow("THE", 2026, 201, "201–250", "the:x"),
                                      sourceRow("ARWU", 2026, 30, "30", "arwu:x"))
                            : List.of(sourceRow("QS", 2025, 17, "=17", "/universities/x"),
                                      sourceRow("THE", 2025, 301, "301–350", "the:x"));
                });

        Map<String, clawer.dto.SourceRankingDTO> bySource = service.getUniversityBySlug("mit").getSourceRankings().stream()
                .collect(java.util.stream.Collectors.toMap(clawer.dto.SourceRankingDTO::getSource, r -> r));

        clawer.dto.SourceRankingDTO qs = bySource.get("QS");
        assertEquals(-3, qs.getRankDelta().getValue());
        assertEquals("up", qs.getRankDelta().getDirection());
        assertEquals(2025, qs.getRankDelta().getPriorYear());
        assertEquals("=17", qs.getRankDelta().getPriorRankDisplay());
        assertNull(qs.getRankDeltaReason());

        clawer.dto.SourceRankingDTO the = bySource.get("THE");
        assertNull(the.getRankDelta().getValue(), "banded ranks give an interval, never a number");
        assertEquals("up", the.getRankDelta().getDirection());
        assertEquals("banded", the.getRankDeltaReason());

        clawer.dto.SourceRankingDTO arwu = bySource.get("ARWU");
        assertNull(arwu.getRankDelta());
        assertEquals("no_prior_row", arwu.getRankDeltaReason());

        // Never composite: the aggregated ranking has no delta field at all.
        assertEquals(2, service.getUniversityBySlug("mit").getAggregatedRanking().getDisplayRank());
    }

    @Test
    void testUniversityWithoutAdmissionRecordReportsNoDataRatherThanNull() {
        University u1 = new University();
        u1.setId(1L);
        u1.setDisplayName("MIT");

        when(universityRepository.findById(1L)).thenReturn(Optional.of(u1));

        UniversityDTO result = universityService.getUniversityById(1L);

        // The UI branches on hasData; a null block or a null summary would make it
        // read every requirement off a null reference.
        AdmissionRequirementsDTO admissions = result.getAdmissionRequirements();
        assertNotNull(admissions);
        assertFalse(admissions.isHasData());
        assertEquals(0, admissions.getDegreeLevelCount());
        assertTrue(admissions.getByDegreeLevel().isEmpty());
        assertNotNull(admissions.getSummary());
        assertNull(admissions.getSummary().getIeltsRequirement());
    }

    @Test
    void testUniversityWithAdmissionRecordExposesStructuredRequirements() {
        University u1 = new University();
        u1.setId(1L);
        u1.setDisplayName("MIT");

        AdmissionRequirementDTO postgraduate = new AdmissionRequirementDTO();
        postgraduate.setDegreeLevel("postgraduate");
        postgraduate.setIeltsRequirement(7.0);
        postgraduate.setToeflRequirement(100);
        // duolingo and gpa stay null: the source published neither, and that has
        // to survive the trip to the client as null rather than 0.
        postgraduate.setApplicationDeadline("2026-01-15");

        AdmissionRequirementsDTO admissions = new AdmissionRequirementsDTO();
        admissions.setHasData(true);
        admissions.setDegreeLevelCount(1);
        admissions.setByDegreeLevel(List.of(postgraduate));
        admissions.setSummary(postgraduate);

        when(universityRepository.findById(1L)).thenReturn(Optional.of(u1));
        when(admissionRecordRepository.findByCanonicalUniversityId(any())).thenReturn(admissions);

        UniversityDTO result = universityService.getUniversityById(1L);

        AdmissionRequirementsDTO actual = result.getAdmissionRequirements();
        assertTrue(actual.isHasData());
        assertEquals(1, actual.getDegreeLevelCount());
        assertEquals("postgraduate", actual.getByDegreeLevel().get(0).getDegreeLevel());
        assertEquals(7.0, actual.getSummary().getIeltsRequirement());
        assertEquals(100, actual.getSummary().getToeflRequirement());
        assertNull(actual.getSummary().getDuolingoRequirement());
        assertNull(actual.getSummary().getGpaRequirement());
        assertEquals("2026-01-15", actual.getSummary().getApplicationDeadline());
    }
}
