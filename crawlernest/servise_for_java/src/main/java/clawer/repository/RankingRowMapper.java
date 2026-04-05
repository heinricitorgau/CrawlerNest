package clawer.repository;

import clawer.domain.ranking.ScopedRankedUniversity;
import org.slf4j.Logger;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.Map;

class RankingRowMapper {
    private final SourceRankParser sourceRankParser;
    private final Logger logger;

    RankingRowMapper(SourceRankParser sourceRankParser, Logger logger) {
        this.sourceRankParser = sourceRankParser;
        this.logger = logger;
    }

    ScopedRankedUniversity map(ResultSet rs) throws SQLException {
        ScopedRankedUniversity row = new ScopedRankedUniversity();
        row.setCanonicalUniversityId(rs.getLong("canonical_university_id"));
        row.setUniversityName(rs.getString("university_name"));
        row.setSlug(rs.getString("slug"));
        row.setCountry(rs.getString("country_name"));

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
        Object rawSourceRanksJson = rs.getObject("source_ranks_json");
        Map<String, Integer> parsedSourceRanks = sourceRankParser.parse(rawSourceRanksJson);
        row.setSourceRanks(parsedSourceRanks);
        row.setSourceCount(parsedSourceRanks.size());
        logger.info(
                "scoped ranking row evidence debug: canonicalUniversityId={}, rawSourceRanksJson={}, parsedSourceRanks={}, sourceCount={}",
                row.getCanonicalUniversityId(),
                rawSourceRanksJson,
                parsedSourceRanks,
                row.getSourceCount()
        );
        return row;
    }
}
