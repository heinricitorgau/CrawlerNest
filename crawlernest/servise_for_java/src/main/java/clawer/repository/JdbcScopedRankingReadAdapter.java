package clawer.repository;

import clawer.domain.ranking.RankingContext;
import clawer.domain.ranking.ScopedRankedUniversity;
import clawer.domain.ranking.ScopedRankingReadAdapter;
import clawer.service.CountryNormalization;
import clawer.service.DatasetScope;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.sql.ResultSet;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.OptionalInt;

@Repository
public class JdbcScopedRankingReadAdapter implements ScopedRankingReadAdapter {
    private static final Logger LOGGER = LoggerFactory.getLogger(JdbcScopedRankingReadAdapter.class);

    /**
     * Search visibility on {@code ranked}. Country is filtered in {@code scoped_base} via
     * {@code warehouse.countries} (FK from {@code canonical_university.country_id}).
     * Binds: normalizedSearch.
     */
    private static final String RANKED_SEARCH_PREDICATE = "(? = '' OR search_score > 0)";

    /**
     * Column list for rows read from {@code ranked} (canonical ranking row + evidence columns for mapping).
     */
    private static final String SELECT_RANKED_ROW_COLUMNS = """
            SELECT
                canonical_university_id,
                university_name,
                slug,
                country_code,
                country_name,
                ranking_year,
                global_rank,
                scope_rank,
                composite_score,
                coverage_ratio,
                ielts_min,
                toefl_min,
                duolingo_min,
                gpa_min,
                application_deadline,
                source_count,
                search_score,
                source_ranks_json,
                aggregation_method_version,
                trust_score,
                trust_level,
                aggregation_explain,
                trust_explain
            """;

    private final JdbcTemplate jdbcTemplate;
    private final RankingRowMapper rankingRowMapper;
    private final DatasetScope datasetScope;

    /**
     * Every public read resolves its edition through {@link DatasetScope} before any
     * SQL is built. The SQL itself only ever filters on a non-null year: the old
     * {@code (? IS NULL OR ranking_year = ?)} form read every edition when no year
     * was passed, which lists each university once per edition as soon as a second
     * one is loaded, and the recommendations endpoint passes no year by default.
     */
    @Autowired
    public JdbcScopedRankingReadAdapter(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper, DatasetScope datasetScope) {
        this.jdbcTemplate = jdbcTemplate;
        this.rankingRowMapper = new RankingRowMapper(new SourceRankParser(objectMapper), objectMapper, LOGGER);
        this.datasetScope = datasetScope;
    }

    public JdbcScopedRankingReadAdapter(JdbcTemplate jdbcTemplate, ObjectMapper objectMapper) {
        this(jdbcTemplate, objectMapper, DatasetScope.standard());
    }

    @Override
    public List<ScopedRankedUniversity> findRankings(
            RankingContext context,
            Integer year,
            String search,
            String countryCode,
            String countryName,
            int page,
            int pageSize
    ) {
        OptionalInt edition = datasetScope.resolveRankingYear(year);
        if (edition.isEmpty()) {
            return List.of();
        }
        logSearchDebug(context, edition.getAsInt(), search);
        ScopedSql scopedSql = buildScopedSql(context, edition.getAsInt(), search, countryCode, countryName, page, pageSize, false, false, null);
        return jdbcTemplate.query(scopedSql.sql(), (rs, rowNum) -> rankingRowMapper.map(rs), scopedSql.args());
    }

    @Override
    public long countRankings(RankingContext context, Integer year, String search, String countryCode, String countryName) {
        OptionalInt edition = datasetScope.resolveRankingYear(year);
        if (edition.isEmpty()) {
            return 0L;
        }
        return countRankingsInEdition(context, edition.getAsInt(), search, countryCode, countryName);
    }

    private long countRankingsInEdition(RankingContext context, int year, String search, String countryCode, String countryName) {
        ScopedSql scopedSql = buildScopedSql(context, year, search, countryCode, countryName, 0, 0, true, false, null);
        Long count = jdbcTemplate.queryForObject(scopedSql.sql(), Long.class, scopedSql.args());
        return count == null ? 0L : count;
    }

    @Override
    public List<Map<String, Object>> findCountryOptions(RankingContext context, Integer year, String search) {
        OptionalInt edition = datasetScope.resolveRankingYear(year);
        if (edition.isEmpty()) {
            return List.of();
        }
        String normalizedSearch = search == null ? "" : search.trim();
        String canonicalCountryNameExpression = CountryNormalization.canonicalCountrySqlExpression("country_name");
        List<Object> argsList = new ArrayList<>();
        StringBuilder sql = appendRankedCtePipeline(context, edition.getAsInt(), normalizedSearch, null, argsList);
        sql.append("""
                SELECT
                    NULL AS country_code,
                    """).append(canonicalCountryNameExpression).append("""
                    AS country_name,
                    COUNT(*) AS country_count
                FROM ranked
                WHERE (? = '' OR search_score > 0)
                  AND country_name IS NOT NULL
                  AND btrim(country_name) <> ''
                GROUP BY 2
                ORDER BY country_count DESC, country_name ASC
                """);
        argsList.add(normalizedSearch);
        return jdbcTemplate.query(
                sql.toString(),
                (rs, rowNum) -> {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("country_code", rs.getString("country_code"));
                    row.put("country_name", rs.getString("country_name"));
                    row.put("country_count", rs.getLong("country_count"));
                    return row;
                },
                argsList.toArray()
        );
    }

    @Override
    public List<ScopedRankedUniversity> findRecommendationCandidates(
            RankingContext context,
            Integer year,
            String country
    ) {
        OptionalInt edition = datasetScope.resolveRankingYear(year);
        if (edition.isEmpty()) {
            return List.of();
        }
        ScopedSql scopedSql = buildScopedSql(context, edition.getAsInt(), null, null, null, 0, 0, false, true, country);
        return jdbcTemplate.query(scopedSql.sql(), (rs, rowNum) -> rankingRowMapper.map(rs), scopedSql.args());
    }

    private ScopedSql buildScopedSql(
            RankingContext context,
            int year,
            String search,
            String countryCode,
            String countryName,
            int page,
            int pageSize,
            boolean countOnly,
            boolean recommendationMode,
            String country
    ) {
        String normalizedSearch = search == null ? "" : search.trim();
        List<Object> argsList = new ArrayList<>();
        String countryNameFilter = (countryName == null || countryName.isBlank()) ? null : countryName.trim();
        LOGGER.info(
                "scoped rankings sql filter debug: scope={}, region={}, requestedCountry={}, normalizedCountry={}, recommendationMode={}",
                context.apiScope(),
                context.region(),
                countryName,
                countryNameFilter,
                recommendationMode
        );
        StringBuilder sql = appendRankedCtePipeline(context, year, normalizedSearch, countryNameFilter, argsList);

        if (countOnly) {
            sql.append("SELECT COUNT(*) FROM ranked WHERE ");
            sql.append(RANKED_SEARCH_PREDICATE);
            argsList.add(normalizedSearch);
            return new ScopedSql(sql.toString(), argsList.toArray());
        }

        sql.append(SELECT_RANKED_ROW_COLUMNS).append("\nFROM ranked\nWHERE 1=1\n");

        if (!recommendationMode) {
            sql.append("  AND ");
            sql.append(RANKED_SEARCH_PREDICATE);
            argsList.add(normalizedSearch);
        }
        if (recommendationMode && country != null && !country.isBlank()) {
            sql.append("  AND ").append(CountryNormalization.canonicalCountrySqlExpression("country_name")).append(" = ?\n");
            argsList.add(CountryNormalization.normalizeCountry(country));
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

    /**
     * Builds the shared {@code WITH ... ranked AS (...)} pipeline used by count, list, country-options, and recommendations.
     *
     * @param countryNameFilter canonical {@code countries.country_name} to match (case-insensitive), or {@code null} for no country filter
     */
    private StringBuilder appendRankedCtePipeline(
            RankingContext context,
            int year,
            String normalizedSearch,
            String countryNameFilter,
            List<Object> argsList
    ) {
        String canonicalCountrySql = CountryNormalization.canonicalCountrySqlExpression("c.country_name");
        StringBuilder sql = new StringBuilder("""
                WITH admission_summary AS (
                    -- University-level requirements only, newest stated intake:
                    -- the rule v_admission_requirement_summary holds for every
                    -- reader. MIN() over admission_record would rank a student
                    -- against the least demanding programme once programme rows exist.
                    SELECT
                        s.canonical_university_id,
                        s.ielts_requirement AS ielts_min,
                        s.toefl_requirement AS toefl_min,
                        s.duolingo_requirement AS duolingo_min,
                        s.gpa_requirement AS gpa_min,
                        s.application_deadline
                    FROM warehouse.v_admission_requirement_summary s
                ),
                global_reference AS (
                    SELECT
                        canonical_university_id,
                        MIN(display_rank) AS global_rank
                    FROM analytics.v_aggregated_rankings_latest
                    WHERE ranking_year = ?::integer
                      AND universe_type = 'global'
                      AND universe_key = 'global'
                    GROUP BY canonical_university_id
                ),
                scoped_reference AS (
                    SELECT
                        canonical_university_id,
                        ranking_year,
                        display_rank,
                        composite_score,
                        coverage_ratio,
                        aggregation_method_version
                    FROM analytics.v_aggregated_rankings_latest
                    WHERE ranking_year = ?::integer
                      AND universe_type = ?
                      AND universe_key = ?
                ),
                scoped_base AS (
                    SELECT
                        cu.canonical_university_id,
                        cu.display_name AS university_name,
                        cu.canonical_slug AS slug,
                        c.country_name AS country_name,
                        c.country_code AS country_code,
                        dp.ranking_year,
                        COALESCE(global_ref.global_rank, ROUND(dp.aggregated_rank)::integer) AS global_rank,
                        scoped_ref.display_rank AS scope_rank,
                        scoped_ref.composite_score,
                        scoped_ref.coverage_ratio,
                        ads.ielts_min,
                        ads.toefl_min,
                        ads.duolingo_min,
                        ads.gpa_min,
                        ads.application_deadline,
                        dp.sources AS source_ranks_json,
                        COALESCE(dp.aggregation_explain ->> 'aggregation_method', scoped_ref.aggregation_method_version) AS aggregation_method_version,
                        COALESCE(c.region_name, '') AS region_name,
                        COALESCE(dp.source_count, (
                            SELECT COUNT(*)
                            FROM jsonb_object_keys(dp.sources)
                        ), 0) AS source_count,
                        dp.trust_score,
                        dp.trust_level,
                        dp.aggregation_explain,
                        dp.trust_explain,
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
                    FROM warehouse.ranking_decision_preview dp
                    JOIN warehouse.canonical_university cu
                      ON cu.display_name_normalized = dp.normalized_university_name
                    LEFT JOIN warehouse.countries c
                      ON c.country_id = cu.country_id
                    JOIN scoped_reference scoped_ref
                      ON scoped_ref.canonical_university_id = cu.canonical_university_id
                     AND scoped_ref.ranking_year = dp.ranking_year
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
                      ON global_ref.canonical_university_id = cu.canonical_university_id
                    LEFT JOIN admission_summary ads
                      ON ads.canonical_university_id = cu.canonical_university_id
                    WHERE dp.ranking_year = ?::integer
                      AND ( ?::text IS NULL OR 
                """);
        sql.append(canonicalCountrySql).append("""
                           = ?::text )
                ),
                ranked AS (
                    SELECT
                        canonical_university_id,
                        university_name,
                        slug,
                        country_code,
                        country_name,
                        ranking_year,
                        global_rank,
                        scope_rank,
                        composite_score,
                        coverage_ratio,
                        ielts_min,
                        toefl_min,
                        duolingo_min,
                        gpa_min,
                        application_deadline,
                        source_ranks_json,
                        aggregation_method_version,
                        source_count,
                        search_score,
                        trust_score,
                        trust_level,
                        aggregation_explain,
                        trust_explain
                    FROM scoped_base
                )
                """);

        argsList.add(year);
        argsList.add(year);
        argsList.add(context.universeType());
        argsList.add(context.universeKey());
        addRepeatedArgs(argsList, normalizedSearch, 24);
        argsList.add(year);
        argsList.add(countryNameFilter);
        argsList.add(countryNameFilter);
        return sql;
    }

    private void addRepeatedArgs(List<Object> args, String value, int count) {
        for (int i = 0; i < count; i++) {
            args.add(value);
        }
    }

    private void logSearchDebug(RankingContext context, int year, String search) {
        String normalizedSearch = search == null ? "" : search.trim();
        if (normalizedSearch.isEmpty()) {
            return;
        }

        long rowsBeforeSearch = countRankingsInEdition(context, year, null, null, null);
        long rowsAfterSearch = countRankingsInEdition(context, year, normalizedSearch, null, null);

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
