package clawer.service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

/**
 * One university's printed rank from each source, for every edition the release holds.
 *
 * <p>Every point says what it is, because a chart that only draws ranks makes two different gaps look
 * alike:
 * <ul>
 *   <li>{@code ranked} -- the source's printed rank, with its band ({@code rankLower}/{@code rankUpper},
 *       upper null for an open band such as "1001+");</li>
 *   <li>{@code edition_not_held} -- this warehouse holds no edition of the source for that year (QS 2017,
 *       THE before 2015). Our gap in the dataset, the same for every university;</li>
 *   <li>{@code not_in_edition} -- the edition is held and this university has no rank in it here: the data
 *       ingested does not include it, or it was not matched. Never "the source declined to rank it".</li>
 * </ul>
 *
 * <p>Nothing is computed across editions here: no composite, no movement. A point records
 * {@code sourceIdentityChanged} when the source's entry for the university differs from the previous ranked
 * point's, so a renderer can break the line where the source may be ranking a different entity.
 */
@Service
public class RankHistoryService {

    public static final String STATUS_RANKED = "ranked";
    public static final String STATUS_EDITION_NOT_HELD = "edition_not_held";
    public static final String STATUS_NOT_IN_EDITION = "not_in_edition";

    private static final String SQL = """
            SELECT DISTINCT ON (rs.source_code, rr.ranking_year)
                   rs.source_code,
                   rr.ranking_year,
                   rr.rank_position,
                   COALESCE(rr.metadata->>'rank_display', rr.metadata->'raw_row'->>'rank') AS rank_display,
                   sm.source_entity_id,
                   COALESCE((rr.metadata->>'suspicious_merge')::boolean, FALSE) AS suspicious_merge
            FROM warehouse.ranking_record rr
            JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
            LEFT JOIN warehouse.source_university_mapping sm ON sm.source_mapping_id = rr.source_mapping_id
            WHERE rr.canonical_university_id = ?
              AND rr.ranking_type = 'world'
              AND rr.universe_type = 'global'
              AND rr.universe_key = 'global'
              AND rr.rank_position IS NOT NULL
            ORDER BY rs.source_code, rr.ranking_year, rr.rank_position ASC
            """;

    private final JdbcTemplate jdbc;
    private final DatasetScope datasetScope;

    public RankHistoryService(JdbcTemplate jdbc, DatasetScope datasetScope) {
        this.jdbc = jdbc;
        this.datasetScope = datasetScope;
    }

    /** The history, or null when the university does not exist. */
    public Map<String, Object> history(long canonicalUniversityId) {
        Integer exists = jdbc.queryForObject(
                "SELECT count(*) FROM warehouse.canonical_university WHERE canonical_university_id = ?",
                Integer.class, canonicalUniversityId);
        if (exists == null || exists == 0) {
            return null;
        }
        Map<String, Map<Integer, Map<String, Object>>> rows = new HashMap<>();
        for (Map<String, Object> row : jdbc.queryForList(SQL, canonicalUniversityId)) {
            rows.computeIfAbsent((String) row.get("source_code"), k -> new HashMap<>())
                    .put(((Number) row.get("ranking_year")).intValue(), row);
        }
        return build(datasetScope.heldYears(), rows);
    }

    /** Pure, for tests: the response for these held years and these rows (source -> year -> row). */
    static Map<String, Object> build(List<Integer> heldYears, Map<String, Map<Integer, Map<String, Object>>> rows) {
        List<Integer> years = heldYears.stream().sorted().toList();
        List<Map<String, Object>> series = new ArrayList<>();
        List<String> caveats = new ArrayList<>();
        caveats.add(AnalyticsService.RANK_HISTORY_CAVEAT);

        for (String source : DatasetScope.DATASET_SOURCES) {
            List<Integer> coverage = DatasetScope.DATASET_COVERAGE.getOrDefault(source, List.of());
            Map<Integer, Map<String, Object>> bySource = rows.getOrDefault(source, Map.of());
            List<Map<String, Object>> points = new ArrayList<>();
            String previousIdentity = null;
            int ranked = 0;
            for (int year : years) {
                Map<String, Object> point = new LinkedHashMap<>();
                point.put("year", year);
                Map<String, Object> row = coverage.contains(year) ? bySource.get(year) : null;
                if (!coverage.contains(year)) {
                    point.put("status", STATUS_EDITION_NOT_HELD);
                } else if (row == null) {
                    point.put("status", STATUS_NOT_IN_EDITION);
                } else {
                    ranked++;
                    String display = (String) row.get("rank_display");
                    int position = ((Number) row.get("rank_position")).intValue();
                    SourceRankDelta.RankBand band = SourceRankDelta.parseRankBand(display);
                    String identity = SourceRankDelta.stableSourceIdentity((String) row.get("source_entity_id"));
                    point.put("status", STATUS_RANKED);
                    point.put("rankDisplay", display != null ? display : Integer.toString(position));
                    point.put("rankLower", band != null ? band.lower() : position);
                    point.put("rankUpper", band != null ? band.upper() : Integer.valueOf(position));
                    point.put("archived", DatasetScope.archiveCaptureDate(source, year) != null);
                    point.put("suspiciousMerge", Boolean.TRUE.equals(row.get("suspicious_merge")));
                    point.put("sourceIdentityChanged",
                            previousIdentity != null && identity != null && !Objects.equals(previousIdentity, identity));
                    if (identity != null) {
                        previousIdentity = identity;
                    }
                    String archived = AnalyticsService.archiveEditionCaveat(source, year);
                    if (archived != null && !caveats.contains(archived)) {
                        caveats.add(archived);
                    }
                }
                points.add(point);
            }
            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("source", source);
            entry.put("rankedEditions", ranked);
            entry.put("points", points);
            series.add(entry);
        }
        if (rows.containsKey("THE")) {
            caveats.add(AnalyticsService.THE_PARTIAL_CAVEAT);
        }
        if (rows.containsKey("ARWU")) {
            caveats.add(AnalyticsService.ARWU_PARTIAL_CAVEAT);
        }

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("years", years);
        data.put("series", series);
        data.put("caveats", List.copyOf(caveats));
        return data;
    }
}
