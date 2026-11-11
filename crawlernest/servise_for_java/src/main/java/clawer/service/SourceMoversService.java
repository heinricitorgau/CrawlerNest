package clawer.service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.OptionalInt;
import java.util.TreeMap;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import clawer.repository.InstitutionLineageRepository;

/**
 * The largest per-source rank movements between one held edition and the one before it.
 *
 * <p>Each movement is {@link SourceRankDelta#compute} -- the same rule the university page uses -- so a mover here
 * is exactly the change that university's page shows. Only exact movements are listed: a banded rank ("201-250")
 * gives an interval, not a position, and is counted rather than ranked. A movement the rule withholds (a changed
 * source entry, an institution merger, a match flagged for review) is counted under its reason, never listed.
 *
 * <p>The prior edition is the previous edition the release holds, as on the university page. When the source has
 * no edition that year (QS 2016), nothing is compared, and the response says why. It never quietly reaches back
 * to an older edition, since that would present a two-year gap as one step.
 */
@Service
public class SourceMoversService {

    public static final int DEFAULT_LIMIT = 20;
    public static final int MAX_LIMIT = 100;

    private static final String SQL = """
            SELECT DISTINCT ON (rr.canonical_university_id, rr.ranking_year)
                   rr.canonical_university_id,
                   rr.ranking_year,
                   cu.display_name,
                   cu.canonical_slug,
                   co.country_name,
                   COALESCE(rr.metadata->>'rank_display', rr.metadata->'raw_row'->>'rank') AS rank_display,
                   sm.source_entity_id,
                   COALESCE((rr.metadata->>'suspicious_merge')::boolean, FALSE) AS suspicious_merge
            FROM warehouse.ranking_record rr
            JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
            JOIN warehouse.canonical_university cu ON cu.canonical_university_id = rr.canonical_university_id
            LEFT JOIN warehouse.countries co ON co.country_id = cu.country_id
            LEFT JOIN warehouse.source_university_mapping sm ON sm.source_mapping_id = rr.source_mapping_id
            WHERE rs.source_code = ?
              AND rr.ranking_year IN (?, ?)
              AND rr.ranking_type = 'world'
              AND rr.universe_type = 'global'
              AND rr.universe_key = 'global'
              AND rr.rank_position IS NOT NULL
            ORDER BY rr.canonical_university_id, rr.ranking_year, rr.rank_position ASC
            """;

    private final JdbcTemplate jdbc;
    private final DatasetScope datasetScope;
    private final InstitutionLineageRepository lineageRepository;

    public SourceMoversService(JdbcTemplate jdbc, DatasetScope datasetScope, InstitutionLineageRepository lineageRepository) {
        this.jdbc = jdbc;
        this.datasetScope = datasetScope;
        this.lineageRepository = lineageRepository;
    }

    /**
     * @throws IllegalArgumentException for a source outside {@link DatasetScope#DATASET_SOURCES} or an edition the
     *                                  release does not hold
     */
    public Map<String, Object> movers(String sourceParam, Integer requestedYear, Integer limitParam) {
        String source = sourceParam == null ? "" : sourceParam.trim().toUpperCase(Locale.ROOT);
        if (!DatasetScope.DATASET_SOURCES.contains(source)) {
            throw new IllegalArgumentException("source must be one of " + DatasetScope.DATASET_SOURCES);
        }
        OptionalInt resolved = datasetScope.resolveRankingYear(requestedYear);
        if (resolved.isEmpty()) {
            throw new IllegalArgumentException("ranking year " + requestedYear + " is not held; held: " + datasetScope.heldYears());
        }
        int year = resolved.getAsInt();
        int limit = limitParam == null ? DEFAULT_LIMIT : Math.max(1, Math.min(MAX_LIMIT, limitParam));
        Integer priorYear = datasetScope.heldYears().stream().filter(y -> y < year).max(Integer::compare).orElse(null);

        Map<String, Object> out = new LinkedHashMap<>();
        out.put("source", source);
        out.put("ranking_year", year);
        out.put("prior_year", priorYear);
        List<String> caveats = new ArrayList<>();
        caveats.add(AnalyticsService.RANK_CHANGE_CAVEAT);

        String withheld = null;
        List<Integer> coverage = DatasetScope.DATASET_COVERAGE.getOrDefault(source, List.of());
        if (priorYear == null) {
            withheld = "no_prior_edition_held";
        } else if (!coverage.contains(year)) {
            withheld = "no_" + source.toLowerCase(Locale.ROOT) + "_edition_" + year;
        } else if (!coverage.contains(priorYear)) {
            withheld = "no_" + source.toLowerCase(Locale.ROOT) + "_edition_" + priorYear;
        }
        if (withheld != null) {
            out.put("withheld_reason", withheld);
            out.put("risers", List.of());
            out.put("fallers", List.of());
            out.put("counts", Map.of());
            out.put("caveats", List.copyOf(caveats));
            return out;
        }

        List<Map<String, Object>> rows = jdbc.queryForList(SQL, source, year, priorYear);
        Map<Long, Map<String, Object>> current = new HashMap<>();
        Map<Long, Map<String, Object>> prior = new HashMap<>();
        for (Map<String, Object> row : rows) {
            long id = ((Number) row.get("canonical_university_id")).longValue();
            (((Number) row.get("ranking_year")).intValue() == year ? current : prior).put(id, row);
        }
        List<Long> both = current.keySet().stream().filter(prior::containsKey).toList();
        var lineage = lineageRepository.findInvolving(both);
        var held = datasetScope.heldYears();

        List<Map<String, Object>> exact = new ArrayList<>();
        Map<String, Integer> counts = new TreeMap<>();
        counts.put("only_in_" + year, (int) current.keySet().stream().filter(id -> !prior.containsKey(id)).count());
        counts.put("only_in_" + priorYear, (int) prior.keySet().stream().filter(id -> !current.containsKey(id)).count());
        for (long id : both) {
            Map<String, Object> c = current.get(id);
            Map<String, Object> p = prior.get(id);
            SourceRankDelta.Result delta = SourceRankDelta.compute(
                    observation(year, source, c), observation(priorYear, source, p), priorYear, id, lineage, held);
            if (delta.value() == null) {
                counts.merge(delta.reason() == null ? "withheld" : delta.reason(), 1, Integer::sum);
                continue;
            }
            counts.merge("exact", 1, Integer::sum);
            if (delta.value() == 0) {
                continue;
            }
            Map<String, Object> mover = new LinkedHashMap<>();
            mover.put("canonicalUniversityId", id);
            mover.put("universityName", c.get("display_name"));
            mover.put("slug", c.get("canonical_slug"));
            mover.put("country", c.get("country_name"));
            mover.put("priorRankDisplay", p.get("rank_display"));
            mover.put("rankDisplay", c.get("rank_display"));
            // Negative is better (a smaller rank number), as in SourceRankDelta.
            mover.put("rankDelta", delta.value());
            exact.add(mover);
        }
        Comparator<Map<String, Object>> byDelta = Comparator.comparingInt(m -> (Integer) m.get("rankDelta"));
        Comparator<Map<String, Object>> tie = Comparator.comparingLong(m -> (Long) m.get("canonicalUniversityId"));
        out.put("risers", exact.stream().filter(m -> (Integer) m.get("rankDelta") < 0)
                .sorted(byDelta.thenComparing(tie)).limit(limit).toList());
        out.put("fallers", exact.stream().filter(m -> (Integer) m.get("rankDelta") > 0)
                .sorted(byDelta.reversed().thenComparing(tie)).limit(limit).toList());
        out.put("counts", counts);
        for (int edition : List.of(year, priorYear)) {
            String archived = AnalyticsService.archiveEditionCaveat(source, edition);
            if (archived != null) {
                caveats.add(archived);
            }
        }
        out.put("caveats", List.copyOf(caveats));
        return out;
    }

    private static SourceRankDelta.Observation observation(int year, String source, Map<String, Object> row) {
        return new SourceRankDelta.Observation(year, source, (String) row.get("rank_display"),
                (String) row.get("source_entity_id"), Boolean.TRUE.equals(row.get("suspicious_merge")));
    }
}
