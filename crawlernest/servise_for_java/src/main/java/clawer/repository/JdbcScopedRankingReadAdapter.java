package clawer.repository;

import clawer.domain.ranking.RankingContext;
import clawer.domain.ranking.ScopedRankedUniversity;
import clawer.domain.ranking.ScopedRankingReadAdapter;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@Repository
public class JdbcScopedRankingReadAdapter implements ScopedRankingReadAdapter {
    private static final Logger LOGGER = LoggerFactory.getLogger(JdbcScopedRankingReadAdapter.class);

    private final JdbcTemplate jdbcTemplate;
    private final ObjectMapper objectMapper;

    public JdbcScopedRankingReadAdapter(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this.jdbcTemplate = jdbcTemplate;
        this.objectMapper = objectMapper;
    }

    @Override
    public List<ScopedRankedUniversity> findRankings(
            RankingContext context,
            Integer year,
            String search,
            int page,
            int pageSize
    ) {
        logSearchDebug(context, year, search);
        ScopedSql scopedSql = buildScopedSql(context, year, search, page, pageSize, false, false, null);
        return jdbcTemplate.query(scopedSql.sql(), this::mapScopedRankedUniversity, scopedSql.args());
    }

    @Override
    public long countRankings(RankingContext context, Integer year, String search) {
        ScopedSql scopedSql = buildScopedSql(context, year, search, 0, 0, true, false, null);
        Long count = jdbcTemplate.queryForObject(scopedSql.sql(), Long.class, scopedSql.args());
        return count == null ? 0L : count;
    }

    @Override
    public List<ScopedRankedUniversity> findRecommendationCandidates(
            RankingContext context,
            Integer year,
            String country
    ) {
        ScopedSql scopedSql = buildScopedSql(context, year, null, 0, 0, false, true, country);
        return jdbcTemplate.query(scopedSql.sql(), this::mapScopedRankedUniversity, scopedSql.args());
    }

    private ScopedSql buildScopedSql(
            RankingContext context,
            Integer year,
            String search,
            int page,
            int pageSize,
            boolean countOnly,
            boolean recommendationMode,
            String country
    ) {
        String normalizedSearch = search == null ? "" : search.trim();
        List<Object> argsList = new ArrayList<>();
        StringBuilder sql = new StringBuilder("""
                WITH admission_summary AS (
                    SELECT
                        cul.canonical_university_id,
                        MIN(ar.ielts_min) FILTER (WHERE ar.ielts_min IS NOT NULL) AS ielts_min
                    FROM warehouse.canonical_university_link cul
                    JOIN warehouse.admission_requirements ar
                      ON ar.university_id = cul.university_id
                    GROUP BY cul.canonical_university_id
                ),
                global_reference AS (
                    SELECT
                        canonical_university_id,
                        MIN(display_rank) AS global_rank
                    FROM analytics.v_aggregated_rankings_latest
                    WHERE (?::integer IS NULL OR ranking_year = ?::integer)
                      AND universe_type = 'global'
                      AND universe_key = 'global'
                    GROUP BY canonical_university_id
                ),
                scoped_base AS (
                    SELECT
                        ar.canonical_university_id,
                        cu.display_name AS university_name,
                        cu.canonical_slug AS slug,
                        c.country_name AS country,
                        ar.ranking_year,
                        COALESCE(global_ref.global_rank, ar.display_rank) AS global_rank,
                        ar.display_rank AS scope_rank,
                        ar.composite_score,
                        ar.coverage_ratio,
                        ads.ielts_min,
                        ar.source_ranks_json,
                        ar.aggregation_method_version,
                        COALESCE(c.region_name, '') AS region_name,
                        COALESCE((
                            SELECT COUNT(*)
                            FROM jsonb_object_keys(ar.source_ranks_json)
                        ), 0) AS source_count,
                        GREATEST(
                            CASE
                                WHEN ? = '' THEN 0
                                WHEN lower(cu.display_name) = lower(?)
                                  OR cu.display_name_normalized = regexp_replace(lower(?), '[^a-z0-9]+', ' ', 'g')
                                THEN 100
                                WHEN lower(cu.display_name) LIKE lower(?) || '%'
                                  OR cu.display_name_normalized LIKE regexp_replace(lower(?), '[^a-z0-9]+', ' ', 'g') || '%'
                                THEN 80
                                WHEN cu.display_name_normalized LIKE regexp_replace(lower(?), '[^a-z0-9]+', ' ', 'g') || ' %'
                                  OR cu.display_name_normalized LIKE '% ' || regexp_replace(lower(?), '[^a-z0-9]+', ' ', 'g') || ' %'
                                  OR cu.display_name_normalized LIKE '% ' || regexp_replace(lower(?), '[^a-z0-9]+', ' ', 'g')
                                THEN 60
                                WHEN char_length(regexp_replace(lower(?), '[^a-z0-9]+', ' ', 'g')) >= 4
                                  AND (
                                      lower(cu.display_name) LIKE '%' || lower(?) || '%'
                                      OR cu.display_name_normalized LIKE '%' || regexp_replace(lower(?), '[^a-z0-9]+', ' ', 'g') || '%'
                                  )
                                THEN 40
                                WHEN char_length(regexp_replace(lower(?), '[^a-z0-9]+', ' ', 'g')) >= 4
                                  AND lower(COALESCE(c.country_name, '')) LIKE '%' || lower(?) || '%'
                                THEN 20
                                ELSE 0
                            END,
                            COALESCE(alias_match.alias_search_score, 0)
                        ) AS search_score
                    FROM analytics.v_aggregated_rankings_latest ar
                    JOIN warehouse.canonical_university cu
                      ON cu.canonical_university_id = ar.canonical_university_id
                    LEFT JOIN warehouse.countries c
                      ON c.country_id = cu.country_id
                    LEFT JOIN LATERAL (
                        SELECT MAX(
                            CASE
                                WHEN ? = '' THEN 0
                                WHEN lower(ua.alias_text) = lower(?)
                                  OR ua.alias_normalized = regexp_replace(lower(?), '[^a-z0-9]+', ' ', 'g')
                                THEN 100
                                WHEN lower(ua.alias_text) LIKE lower(?) || '%'
                                  OR ua.alias_normalized LIKE regexp_replace(lower(?), '[^a-z0-9]+', ' ', 'g') || '%'
                                THEN 80
                                WHEN ua.alias_normalized LIKE regexp_replace(lower(?), '[^a-z0-9]+', ' ', 'g') || ' %'
                                  OR ua.alias_normalized LIKE '% ' || regexp_replace(lower(?), '[^a-z0-9]+', ' ', 'g') || ' %'
                                  OR ua.alias_normalized LIKE '% ' || regexp_replace(lower(?), '[^a-z0-9]+', ' ', 'g')
                                THEN 60
                                WHEN char_length(regexp_replace(lower(?), '[^a-z0-9]+', ' ', 'g')) >= 4
                                  AND (
                                      lower(ua.alias_text) LIKE '%' || lower(?) || '%'
                                      OR ua.alias_normalized LIKE '%' || regexp_replace(lower(?), '[^a-z0-9]+', ' ', 'g') || '%'
                                  )
                                THEN 40
                                ELSE 0
                            END
                        ) AS alias_search_score
                        FROM warehouse.university_alias ua
                        WHERE ua.canonical_university_id = cu.canonical_university_id
                    ) alias_match ON TRUE
                    LEFT JOIN global_reference global_ref
                      ON global_ref.canonical_university_id = ar.canonical_university_id
                    LEFT JOIN admission_summary ads
                      ON ads.canonical_university_id = ar.canonical_university_id
                    WHERE (?::integer IS NULL OR ar.ranking_year = ?::integer)
                      AND ar.universe_type = ?
                      AND ar.universe_key = ?
                ),
                ranked AS (
                    SELECT
                        canonical_university_id,
                        university_name,
                        slug,
                        country,
                        ranking_year,
                        global_rank,
                        scope_rank,
                        composite_score,
                        coverage_ratio,
                        ielts_min,
                        source_ranks_json,
                        aggregation_method_version,
                        source_count,
                        search_score
                    FROM scoped_base
                )
                """);

        argsList.add(year);
        argsList.add(year);
        addRepeatedArgs(argsList, normalizedSearch, 24);
        argsList.add(year);
        argsList.add(year);
        argsList.add(context.universeType());
        argsList.add(context.universeKey());

        if (countOnly) {
            sql.append("""
                    SELECT COUNT(*)
                    FROM ranked
                    WHERE (? = '' OR search_score > 0)
                    """);
            argsList.add(normalizedSearch);
            return new ScopedSql(sql.toString(), argsList.toArray());
        }

        sql.append("""
                SELECT
                    canonical_university_id,
                    university_name,
                    slug,
                    country,
                    ranking_year,
                    global_rank,
                    scope_rank,
                    composite_score,
                    coverage_ratio,
                    ielts_min,
                    source_ranks_json,
                    aggregation_method_version,
                    source_count
                FROM ranked
                WHERE 1=1
                """);

        if (!recommendationMode) {
            sql.append(" AND (? = '' OR search_score > 0)");
            argsList.add(normalizedSearch);
        }
        if (recommendationMode && country != null && !country.isBlank()) {
            sql.append(" AND country = ?\n");
            argsList.add(country);
        }

        sql.append("""
                ORDER BY
                    CASE WHEN ? THEN 0 ELSE search_score END DESC,
                    CASE WHEN scope_rank IS NULL THEN 1 ELSE 0 END,
                    scope_rank ASC,
                    university_name ASC,
                    canonical_university_id ASC
                """);
        argsList.add(recommendationMode);

        if (!recommendationMode) {
            sql.append(" LIMIT ? OFFSET ?");
            argsList.add(pageSize);
            argsList.add(page * pageSize);
        }

        return new ScopedSql(sql.toString(), argsList.toArray());
    }

    private ScopedRankedUniversity mapScopedRankedUniversity(ResultSet rs, int rowNum) throws SQLException {
        ScopedRankedUniversity row = new ScopedRankedUniversity();
        row.setCanonicalUniversityId(rs.getLong("canonical_university_id"));
        row.setUniversityName(rs.getString("university_name"));
        row.setSlug(rs.getString("slug"));
        row.setCountry(rs.getString("country"));

        int rankingYear = rs.getInt("ranking_year");
        row.setRankingYear(rs.wasNull() ? null : rankingYear);

        int globalRank = rs.getInt("global_rank");
        row.setGlobalRank(rs.wasNull() ? null : globalRank);

        int scopeRank = rs.getInt("scope_rank");
        row.setScopeRank(rs.wasNull() ? null : scopeRank);

        double compositeScore = rs.getDouble("composite_score");
        row.setCompositeScore(rs.wasNull() ? null : compositeScore);

        double coverageRatio = rs.getDouble("coverage_ratio");
        row.setCoverageRatio(rs.wasNull() ? null : coverageRatio);

        double ieltsMin = rs.getDouble("ielts_min");
        row.setIeltsMin(rs.wasNull() ? null : ieltsMin);

        row.setAggregationMethodVersion(rs.getString("aggregation_method_version"));
        row.setSourceCount(rs.getInt("source_count"));
        row.setSourceRanks(parseJsonMap(rs.getObject("source_ranks_json")));
        return row;
    }

    private Map<String, Integer> parseJsonMap(Object value) {
        if (value == null) {
            return new LinkedHashMap<>();
        }
        try {
            Map<String, Object> raw = objectMapper.readValue(value.toString(), new TypeReference<>() {});
            Map<String, Integer> parsed = new LinkedHashMap<>();
            for (Map.Entry<String, Object> entry : raw.entrySet()) {
                if (entry.getValue() != null) {
                    parsed.put(entry.getKey().toUpperCase(Locale.ROOT), Integer.parseInt(entry.getValue().toString()));
                }
            }
            return parsed;
        } catch (Exception e) {
            return new LinkedHashMap<>();
        }
    }

    private void addRepeatedArgs(List<Object> args, String value, int count) {
        for (int i = 0; i < count; i++) {
            args.add(value);
        }
    }

    private void logSearchDebug(RankingContext context, Integer year, String search) {
        String normalizedSearch = search == null ? "" : search.trim();
        if (normalizedSearch.isEmpty()) {
            return;
        }

        long rowsBeforeSearch = countRankings(context, year, null);
        long rowsAfterSearch = countRankings(context, year, normalizedSearch);

        LOGGER.info(
                "Scoped ranking search debug: search='{}', scope='{}', region='{}', whereClause='LOWER(university_name) LIKE %search% OR LOWER(country_name) LIKE %search% OR alias match', rowsBeforeSearch={}, rowsAfterSearch={}",
                normalizedSearch,
                context.apiScope(),
                context.region(),
                rowsBeforeSearch,
                rowsAfterSearch
        );
    }

    private record ScopedSql(String sql, Object[] args) {}
}
