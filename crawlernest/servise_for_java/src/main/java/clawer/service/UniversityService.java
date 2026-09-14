package clawer.service;

import clawer.dto.RankDeltaDTO;
import clawer.dto.RankingDTO;
import clawer.dto.SourceRankingDTO;
import clawer.dto.UniversityDTO;
import clawer.model.University;
import clawer.repository.AdmissionRecordRepository;
import clawer.repository.InstitutionLineageRepository;
import clawer.repository.UniversityRepository;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Service for handling University-related business logic.
 */
@Service
public class UniversityService {
    private static final List<String> SOURCE_PRIORITY = List.of("QS", "THE", "ARWU");

    private final UniversityRepository universityRepository;
    private final AdmissionRecordRepository admissionRecordRepository;
    private final JdbcTemplate jdbcTemplate;
    private final DatasetScope datasetScope;
    private final InstitutionLineageRepository institutionLineageRepository;

    public UniversityService(
            UniversityRepository universityRepository,
            AdmissionRecordRepository admissionRecordRepository,
            JdbcTemplate jdbcTemplate,
            DatasetScope datasetScope,
            InstitutionLineageRepository institutionLineageRepository
    ) {
        this.universityRepository = universityRepository;
        this.admissionRecordRepository = admissionRecordRepository;
        this.jdbcTemplate = jdbcTemplate;
        this.datasetScope = datasetScope;
        this.institutionLineageRepository = institutionLineageRepository;
    }

    public List<UniversityDTO> getAllUniversities(int page, int size) {
        Pageable pageable = PageRequest.of(page, size);
        return universityRepository.findAll(pageable).stream()
                .map(this::convertToDTO)
                .collect(Collectors.toList());
    }

    public UniversityDTO getUniversityById(Long id) {
        return universityRepository.findById(id)
                .map(this::convertToDTO)
                .orElse(null);
    }

    public UniversityDTO getUniversityBySlug(String slug) {
        UniversityDTO legacy = universityRepository.findBySchoolSlug(slug)
                .map(this::convertToCanonicalBackedDTO)
                .orElse(null);

        if (legacy != null) {
            return legacy;
        }

        // Fallback: rankings UI uses canonical_slug (warehouse.canonical_university),
        // while the legacy university page endpoint originally queried only warehouse.universities.school_slug.
        // When a canonical university has no legacy university row/link, return a canonical-based DTO instead of 404.
        return getUniversityByCanonicalSlug(slug);
    }

    private UniversityDTO getUniversityByCanonicalSlug(String canonicalSlug) {
        String canonicalSql = """
                SELECT cu.canonical_university_id,
                       cu.display_name,
                       co.country_name
                FROM warehouse.canonical_university cu
                LEFT JOIN warehouse.countries co
                       ON co.country_id = cu.country_id
                WHERE cu.canonical_slug = ?
                LIMIT 1
                """;

        List<Map<String, Object>> canonicalRows = jdbcTemplate.query(
                canonicalSql,
                new Object[]{canonicalSlug},
                (rs, rowNum) -> {
                    Map<String, Object> m = new java.util.HashMap<>();
                    m.put("canonical_university_id", rs.getLong("canonical_university_id"));
                    m.put("display_name", rs.getString("display_name"));
                    m.put("country_name", rs.getString("country_name"));
                    return m;
                }
        );
        if (canonicalRows.isEmpty()) {
            return null;
        }

        Map<String, Object> r = canonicalRows.get(0);
        long canonicalUniversityId = ((Number) r.get("canonical_university_id")).longValue();

        UniversityDTO dto = new UniversityDTO();
        dto.setCanonicalUniversityId(canonicalUniversityId);
        dto.setSlug(canonicalSlug);
        dto.setUniversityName((String) r.get("display_name"));
        dto.setCountry((String) r.get("country_name"));
        hydrateCanonicalRankings(dto, canonicalUniversityId);

        dto.setAdmissionRequirements(admissionRecordRepository.findByCanonicalUniversityId(dto.getCanonicalUniversityId()));
        clawer.dto.DataQualityDTO quality = new clawer.dto.DataQualityDTO();
        quality.setRecommendationConfidence(0.9);
        quality.setConfidenceLabel("High");
        quality.setConfidenceReason("Rankings are fully merged and verified");
        dto.setDataQuality(quality);
        return dto;
    }

    private UniversityDTO convertToCanonicalBackedDTO(University university) {
        UniversityDTO dto = new UniversityDTO();
        dto.setSlug(university.getSchoolSlug());
        dto.setUniversityName(university.getDisplayName());
        dto.setCountry(university.getCountry() != null ? university.getCountry().getCountryName() : null);
        Long canonicalUniversityId = resolveCanonicalUniversityId(university.getId());
        dto.setCanonicalUniversityId(canonicalUniversityId);

        if (canonicalUniversityId != null) {
            hydrateCanonicalRankings(dto, canonicalUniversityId);
        } else {
            dto.setAggregatedRanking(null);
            dto.setSourceRankings(List.of());
            dto.setRankingEvidence(List.of());
        }

        dto.setAdmissionRequirements(admissionRecordRepository.findByCanonicalUniversityId(dto.getCanonicalUniversityId()));
        clawer.dto.DataQualityDTO quality = new clawer.dto.DataQualityDTO();
        quality.setRecommendationConfidence(0.9);
        quality.setConfidenceLabel("High");
        quality.setConfidenceReason("Rankings are fully merged and verified");
        dto.setDataQuality(quality);
        return dto;
    }

    private UniversityDTO convertToDTO(University university) {
        UniversityDTO dto = new UniversityDTO();
        dto.setCanonicalUniversityId(university.getId());
        dto.setSlug(university.getSchoolSlug());
        dto.setUniversityName(university.getDisplayName());
        dto.setCountry(university.getCountry() != null ? university.getCountry().getCountryName() : null);

        if (university.getRankings() != null && !university.getRankings().isEmpty()) {
            clawer.dto.AggregatedRankingDTO aggRank = university.getRankings().stream()
                    .filter(r -> r.getRankStart() != null)
                    .map(r -> {
                        clawer.dto.AggregatedRankingDTO aDto = new clawer.dto.AggregatedRankingDTO();
                        aDto.setDisplayRank(r.getRankStart());
                        aDto.setCompositeScore(r.getScore());
                        aDto.setRankingYear(r.getRankingYear());
                        aDto.setAggregationMethodVersion("v1");
                        return aDto;
                    })
                    .findFirst()
                    .orElse(null);
            dto.setAggregatedRanking(aggRank);

            List<SourceRankingDTO> sourceRankings = university.getRankings().stream()
                    .filter(r -> r.getRankStart() != null)
                    .collect(Collectors.toMap(
                            r -> r.getRankingSource() + "-" + r.getRankingYear(),
                            r -> r,
                            (r1, r2) -> r1.getRankStart() < r2.getRankStart() ? r1 : r2
                    ))
                    .values().stream()
                    .map(ranking -> {
                        SourceRankingDTO rDto = new SourceRankingDTO();
                        rDto.setSource(ranking.getRankingSource());
                        rDto.setYear(ranking.getRankingYear());
                        rDto.setRank(ranking.getRankStart());
                        rDto.setScore(ranking.getScore());
                        return rDto;
                    }).collect(Collectors.toList());
            dto.setSourceRankings(sourceRankings);
            dto.setRankingEvidence(sourceRankings);
        } else {
            dto.setSourceRankings(List.of());
            dto.setRankingEvidence(List.of());
        }

        dto.setAdmissionRequirements(
                admissionRecordRepository.findByCanonicalUniversityId(resolveCanonicalUniversityId(university.getId()))
        );
        clawer.dto.DataQualityDTO quality = new clawer.dto.DataQualityDTO();
        quality.setRecommendationConfidence(0.9);
        quality.setConfidenceLabel("High");
        quality.setConfidenceReason("Rankings are fully merged and verified");
        dto.setDataQuality(quality);
        return dto;
    }

    private Long resolveCanonicalUniversityId(Long universityId) {
        String canonicalLinkSql = """
                SELECT cul.canonical_university_id
                FROM warehouse.canonical_university_link cul
                WHERE cul.university_id = ?
                LIMIT 1
                """;

        List<Long> canonicalIds = jdbcTemplate.query(
                canonicalLinkSql,
                new Object[]{universityId},
                (rs, rowNum) -> rs.getLong("canonical_university_id")
        );
        return canonicalIds.isEmpty() ? null : canonicalIds.get(0);
    }

    private void hydrateCanonicalRankings(UniversityDTO dto, Long canonicalUniversityId) {
        // The default edition, not "the newest row for this university": that would
        // hand a university missing from the current edition its rank from an older
        // or unreleased one, labelled as current.
        String aggSql = """
                SELECT ranking_year, display_rank, composite_score, aggregation_method_version
                FROM analytics.v_aggregated_rankings_latest
                WHERE canonical_university_id = ?
                  AND ranking_year = ?
                  AND universe_type = 'global'
                  AND universe_key = 'global'
                """;

        List<Map<String, Object>> aggRows = jdbcTemplate.query(
                aggSql,
                new Object[]{canonicalUniversityId, datasetScope.defaultRankingYear()},
                (rs, rowNum) -> {
                    Map<String, Object> m = new java.util.HashMap<>();
                    m.put("ranking_year", rs.getInt("ranking_year"));
                    m.put("display_rank", rs.getObject("display_rank"));
                    m.put("composite_score", rs.getObject("composite_score"));
                    m.put("aggregation_method_version", rs.getString("aggregation_method_version"));
                    return m;
                }
        );

        if (aggRows.isEmpty()) {
            dto.setAggregatedRanking(null);
            dto.setSourceRankings(List.of());
            dto.setRankingEvidence(List.of());
            return;
        }

        Map<String, Object> ar = aggRows.get(0);
        int rankingYear = ((Number) ar.get("ranking_year")).intValue();

        clawer.dto.AggregatedRankingDTO aggregated = new clawer.dto.AggregatedRankingDTO();
        aggregated.setRankingYear(rankingYear);

        Object displayRankObj = ar.get("display_rank");
        aggregated.setDisplayRank(
                displayRankObj == null ? null : ((Number) displayRankObj).intValue()
        );

        Object compositeScoreObj = ar.get("composite_score");
        Double compositeScore = null;
        if (compositeScoreObj instanceof BigDecimal) {
            compositeScore = ((BigDecimal) compositeScoreObj).doubleValue();
        } else if (compositeScoreObj instanceof Number) {
            compositeScore = ((Number) compositeScoreObj).doubleValue();
        }
        aggregated.setCompositeScore(compositeScore);
        aggregated.setAggregationMethodVersion((String) ar.get("aggregation_method_version"));
        dto.setAggregatedRanking(aggregated);

        dto.setSourceRankings(loadRankingEvidence(canonicalUniversityId, rankingYear));
        dto.setRankingEvidence(dto.getSourceRankings());
    }

    private static final String SOURCE_ROWS_SQL = """
            WITH ranked_source_rows AS (
                SELECT rs.source_code,
                       rr.ranking_year,
                       rr.rank_position,
                       rr.score,
                       COALESCE(rr.metadata->>'rank_display', rr.metadata->'raw_row'->>'rank') AS rank_display,
                       sm.source_entity_id,
                       COALESCE((rr.metadata->>'suspicious_merge')::boolean, FALSE) AS suspicious_merge,
                       ROW_NUMBER() OVER (
                           PARTITION BY rs.source_code
                           ORDER BY rr.rank_position ASC NULLS LAST, rr.score DESC NULLS LAST
                       ) AS row_num
                FROM warehouse.ranking_record rr
                JOIN warehouse.ranking_source rs
                  ON rs.ranking_source_id = rr.ranking_source_id
                LEFT JOIN warehouse.source_university_mapping sm
                  ON sm.source_mapping_id = rr.source_mapping_id
                WHERE rr.canonical_university_id = ?
                  AND rr.ranking_year = ?
                  AND rr.ranking_type = 'world'
                  AND rr.universe_type = 'global'
                  AND rr.universe_key = 'global'
                  AND rr.rank_position IS NOT NULL
            )
            SELECT source_code,
                   ranking_year,
                   rank_position,
                   score,
                   rank_display,
                   source_entity_id,
                   suspicious_merge
            FROM ranked_source_rows
            WHERE row_num = 1
            """;

    /**
     * This edition's per-source ranks, each with its movement since the prior held edition.
     *
     * <p>The delta is computed source by source from the printed ranks
     * ({@link SourceRankDelta}); nothing here subtracts {@code display_rank} or a
     * composite score. The prior edition is the next-older one {@link DatasetScope}
     * holds -- an ingested but unreleased edition is never read, so a shadow load
     * cannot produce a movement.
     *
     * <p>Public so {@link ComparisonService} shows the same per-source ranks and
     * movements as the university page rather than computing its own.
     */
    public List<SourceRankingDTO> loadRankingEvidence(Long canonicalUniversityId, int rankingYear) {
        List<Map<String, Object>> srcRows = querySourceRows(canonicalUniversityId, rankingYear);
        if (srcRows.isEmpty()) {
            return List.of();
        }

        Integer heldPriorYear = datasetScope.heldYears().stream()
                .filter(year -> year < rankingYear)
                .max(Integer::compare)
                .orElse(null);
        // With no older held edition the comparison is with the edition before, which
        // SourceRankDelta withholds as single_year_dataset without reading anything.
        int priorYear = heldPriorYear != null ? heldPriorYear : rankingYear - 1;
        Map<String, Map<String, Object>> priorBySource = heldPriorYear == null
                ? Map.of()
                : querySourceRows(canonicalUniversityId, heldPriorYear).stream()
                        .collect(Collectors.toMap(row -> (String) row.get("source_code"), row -> row, (a, b) -> a));
        List<InstitutionLineage.Event> lineage = heldPriorYear == null
                ? List.of()
                : institutionLineageRepository.findInvolving(List.of(canonicalUniversityId));

        return srcRows.stream()
                .map(row -> {
                    SourceRankingDTO dto = toSourceRanking(row);
                    Map<String, Object> prior = priorBySource.get(dto.getSource());
                    SourceRankDelta.Result delta = SourceRankDelta.compute(
                            toObservation(row), prior == null ? null : toObservation(prior),
                            priorYear, canonicalUniversityId, lineage, datasetScope.heldYears());
                    applyDelta(dto, delta, prior);
                    return dto;
                })
                .sorted(Comparator
                        .comparingInt((SourceRankingDTO row) -> sourcePriority(row.getSource()))
                        .thenComparing(SourceRankingDTO::getSource, Comparator.nullsLast(String::compareTo)))
                .collect(Collectors.toList());
    }

    private List<Map<String, Object>> querySourceRows(Long canonicalUniversityId, int rankingYear) {
        return jdbcTemplate.query(
                SOURCE_ROWS_SQL,
                new Object[]{canonicalUniversityId, rankingYear},
                (rs, rowNum) -> {
                    Map<String, Object> m = new java.util.HashMap<>();
                    m.put("source_code", rs.getString("source_code"));
                    m.put("ranking_year", rs.getInt("ranking_year"));
                    m.put("rank_position", rs.getObject("rank_position"));
                    m.put("score", rs.getObject("score"));
                    m.put("rank_display", rs.getString("rank_display"));
                    m.put("source_entity_id", rs.getString("source_entity_id"));
                    m.put("suspicious_merge", rs.getBoolean("suspicious_merge"));
                    return m;
                }
        );
    }

    private static SourceRankDelta.Observation toObservation(Map<String, Object> row) {
        return new SourceRankDelta.Observation(
                ((Number) row.get("ranking_year")).intValue(),
                (String) row.get("source_code"),
                (String) row.get("rank_display"),
                (String) row.get("source_entity_id"),
                Boolean.TRUE.equals(row.get("suspicious_merge")));
    }

    private static void applyDelta(SourceRankingDTO dto, SourceRankDelta.Result delta, Map<String, Object> prior) {
        dto.setRankDeltaReason(delta.reason());
        if (!delta.compared()) {
            dto.setRankDelta(null);
            return;
        }
        RankDeltaDTO out = new RankDeltaDTO();
        out.setPriorYear(delta.priorYear());
        out.setCurrentYear(delta.currentYear());
        out.setPriorRankDisplay(prior == null ? null : (String) prior.get("rank_display"));
        out.setValue(delta.value());
        out.setMin(delta.min());
        out.setMax(delta.max());
        out.setDirection(delta.direction());
        dto.setRankDelta(out);
    }

    private SourceRankingDTO toSourceRanking(Map<String, Object> row) {
        SourceRankingDTO sourceRanking = new SourceRankingDTO();
        sourceRanking.setSource((String) row.get("source_code"));
        sourceRanking.setYear(((Number) row.get("ranking_year")).intValue());

        Object rankObj = row.get("rank_position");
        sourceRanking.setRank(rankObj == null ? null : ((Number) rankObj).intValue());
        sourceRanking.setRankDisplay((String) row.get("rank_display"));

        Object scoreObj = row.get("score");
        Double score = null;
        if (scoreObj instanceof BigDecimal) {
            score = ((BigDecimal) scoreObj).doubleValue();
        } else if (scoreObj instanceof Number) {
            score = ((Number) scoreObj).doubleValue();
        }
        sourceRanking.setScore(score);
        return sourceRanking;
    }

    private int sourcePriority(String source) {
        int index = SOURCE_PRIORITY.indexOf(source);
        return index >= 0 ? index : SOURCE_PRIORITY.size();
    }
}
