package clawer.repository;

import clawer.dto.RankingDTO;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.List;

@Repository
public class JdbcAggregatedRankingReadRepository implements AggregatedRankingReadRepository {

    private final JdbcTemplate jdbcTemplate;

    public JdbcAggregatedRankingReadRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @Override
    public List<RankingDTO> findRankings(Integer year, int offset, int limit) {
        return jdbcTemplate.query(
                """
                SELECT
                    cu.canonical_university_id,
                    cu.display_name AS university_name,
                    cu.canonical_slug AS slug,
                    c.country_name AS country,
                    ar.display_rank AS aggregated_rank,
                    ar.composite_score,
                    ar.ranking_year,
                    COALESCE((
                        SELECT COUNT(*)
                        FROM jsonb_object_keys(ar.source_ranks_json)
                    ), 0) AS source_count
                FROM analytics.v_aggregated_rankings_latest ar
                JOIN warehouse.canonical_university cu
                  ON cu.canonical_university_id = ar.canonical_university_id
                LEFT JOIN warehouse.countries c
                  ON c.country_id = cu.country_id
                WHERE (? IS NULL OR ar.ranking_year = ?)
                ORDER BY
                    CASE WHEN ar.display_rank IS NULL THEN 1 ELSE 0 END,
                    ar.display_rank ASC,
                    cu.display_name ASC,
                    cu.canonical_university_id ASC
                OFFSET ? LIMIT ?
                """,
                (rs, rowNum) -> mapRanking(rs),
                year, year, offset, limit
        );
    }

    @Override
    public long countRankings(Integer year) {
        Long count = jdbcTemplate.queryForObject(
                """
                SELECT COUNT(*)
                FROM analytics.v_aggregated_rankings_latest ar
                WHERE (? IS NULL OR ar.ranking_year = ?)
                """,
                Long.class,
                year, year
        );
        return count == null ? 0L : count;
    }

    private RankingDTO mapRanking(ResultSet rs) throws SQLException {
        RankingDTO dto = new RankingDTO();
        dto.setCanonicalUniversityId(rs.getLong("canonical_university_id"));
        dto.setUniversityName(rs.getString("university_name"));
        dto.setSlug(rs.getString("slug"));
        dto.setCountry(rs.getString("country"));

        int aggregatedRank = rs.getInt("aggregated_rank");
        dto.setAggregatedRank(rs.wasNull() ? null : aggregatedRank);

        double compositeScore = rs.getDouble("composite_score");
        dto.setCompositeScore(rs.wasNull() ? null : compositeScore);

        int rankingYear = rs.getInt("ranking_year");
        dto.setRankingYear(rs.wasNull() ? null : rankingYear);

        dto.setPrimarySource("AGGREGATED");
        dto.setSourceCount(rs.getInt("source_count"));
        return dto;
    }
}
