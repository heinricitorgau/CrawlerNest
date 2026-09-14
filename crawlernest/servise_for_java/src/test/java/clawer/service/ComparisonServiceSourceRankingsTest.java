package clawer.service;

import clawer.dto.RankDeltaDTO;
import clawer.dto.SourceRankingDTO;
import clawer.model.UniversityComparisonResult;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * The comparison carries each source's printed rank and movement, from the same
 * computation as the university page.
 *
 * <p>It used to send only {@code sourceRanks}: rank_position, a band's lower bound,
 * with no movement at all -- so a comparison table could either show no change or
 * work one out itself by subtracting positions, which is the precision and composite
 * error {@link SourceRankDelta} exists to prevent.
 */
class ComparisonServiceSourceRankingsTest {

    private static final long LEFT = 11L;
    private static final long RIGHT = 22L;

    @Test
    void eachUniversityCarriesItsEvidenceForTheResolvedEdition() {
        DatasetScope scope = DatasetScope.standard();
        int edition = scope.defaultRankingYear();
        UniversityService universities = mock(UniversityService.class);
        SourceRankingDTO banded = sourceRanking("THE", "551–560", "601–610", "up", "banded");
        SourceRankingDTO merged = sourceRanking("QS", "40", null, null, "entity_changed");
        when(universities.loadRankingEvidence(LEFT, edition)).thenReturn(List.of(banded));
        when(universities.loadRankingEvidence(RIGHT, edition)).thenReturn(List.of(merged));

        ComparisonService service = new ComparisonService(new CandidateJdbc(), new ObjectMapper(), scope, universities);
        UniversityComparisonResult result = service.compareUniversities(List.of(String.valueOf(LEFT), String.valueOf(RIGHT)), null);

        Map<?, ?> byName = (Map<?, ?>) result.getComparison().get("universities");
        assertSame(banded, ((List<?>) payload(byName, LEFT).get("sourceRankings")).get(0));
        assertSame(merged, ((List<?>) payload(byName, RIGHT).get("sourceRankings")).get(0));
        verify(universities).loadRankingEvidence(LEFT, edition);
        verify(universities).loadRankingEvidence(RIGHT, edition);
    }

    @Test
    void aServiceBuiltWithoutEvidenceSendsAnEmptyListNotAGuess() {
        ComparisonService service = new ComparisonService(new CandidateJdbc(), new ObjectMapper());
        UniversityComparisonResult result = service.compareUniversities(List.of(String.valueOf(LEFT), String.valueOf(RIGHT)), null);

        Map<?, ?> byName = (Map<?, ?>) result.getComparison().get("universities");
        for (long id : new long[]{LEFT, RIGHT}) {
            assertEquals(List.of(), payload(byName, id).get("sourceRankings"));
            assertTrue(payload(byName, id).containsKey("sourceRanks"), "the existing field stays");
        }
    }

    @Test
    void anUnheldYearIsRefusedBeforeAnyEvidenceIsRead() {
        UniversityService universities = mock(UniversityService.class);
        ComparisonService service = new ComparisonService(new CandidateJdbc(), new ObjectMapper(), DatasetScope.standard(), universities);
        assertThrows(IllegalArgumentException.class,
                () -> service.compareUniversities(List.of(String.valueOf(LEFT), String.valueOf(RIGHT)), 1999));
        verify(universities, never()).loadRankingEvidence(anyLong(), anyInt());
    }

    private static Map<?, ?> payload(Map<?, ?> byName, long id) {
        return byName.values().stream()
                .map(value -> (Map<?, ?>) value)
                .filter(value -> Long.valueOf(id).equals(value.get("canonicalUniversityId")))
                .findFirst()
                .orElseThrow();
    }

    private static SourceRankingDTO sourceRanking(String source, String display, String priorDisplay, String direction, String reason) {
        SourceRankingDTO dto = new SourceRankingDTO();
        dto.setSource(source);
        dto.setRankDisplay(display);
        dto.setRankDeltaReason(reason);
        if (direction != null) {
            RankDeltaDTO delta = new RankDeltaDTO();
            delta.setPriorYear(2025);
            delta.setCurrentYear(2026);
            delta.setPriorRankDisplay(priorDisplay);
            delta.setMin(-59);
            delta.setMax(-41);
            delta.setDirection(direction);
            dto.setRankDelta(delta);
        }
        return dto;
    }

    /** Answers the candidate lookup with one row per numeric identifier. */
    private static final class CandidateJdbc extends JdbcTemplate {
        @Override
        public <T> List<T> query(String sql, RowMapper<T> rowMapper, Object... args) {
            long id = ((Number) args[0]).longValue();
            try {
                return List.of(rowMapper.mapRow(row(id), 0));
            } catch (SQLException e) {
                throw new IllegalStateException(e);
            }
        }

        private static ResultSet row(long id) throws SQLException {
            ResultSet rs = mock(ResultSet.class);
            when(rs.getLong("canonical_university_id")).thenReturn(id);
            when(rs.getString("university_name")).thenReturn("University " + id);
            when(rs.getString("country")).thenReturn("Nowhere");
            when(rs.getInt("ranking_year")).thenReturn(DatasetScope.DEFAULT_RANKING_YEAR);
            when(rs.getInt("aggregated_rank")).thenReturn((int) id);
            when(rs.getDouble("composite_score")).thenReturn(80.0);
            when(rs.getDouble("coverage_ratio")).thenReturn(1.0);
            when(rs.getDouble("ielts_min")).thenReturn(6.5);
            when(rs.getString("aggregation_method_version")).thenReturn("test");
            when(rs.getObject("source_ranks_json")).thenReturn("{\"QS\": " + id + "}");
            when(rs.getObject("source_scores_json")).thenReturn("{\"QS\": 80.0}");
            when(rs.getInt("match_priority")).thenReturn(0);
            return rs;
        }
    }
}
