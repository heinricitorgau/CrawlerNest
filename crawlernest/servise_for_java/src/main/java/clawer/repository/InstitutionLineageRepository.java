package clawer.repository;

import clawer.service.InstitutionLineage;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;
import java.util.stream.Collectors;

/** Reads {@code warehouse.institution_lineage}. */
@Repository
public class InstitutionLineageRepository {
    private static final Logger LOGGER = LoggerFactory.getLogger(InstitutionLineageRepository.class);

    private final JdbcTemplate jdbcTemplate;

    public InstitutionLineageRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * Every event naming any of these universities on either side.
     *
     * <p>Returns an empty list, with a warning, on a database bootstrapped before
     * the table existed. That cannot turn into a movement claim: the only Java
     * caller withholds every delta regardless and uses this only to say why.
     */
    public List<InstitutionLineage.Event> findInvolving(Collection<Long> canonicalUniversityIds) {
        if (canonicalUniversityIds.isEmpty()) {
            return List.of();
        }
        Boolean present = jdbcTemplate.queryForObject(
                "SELECT to_regclass('warehouse.institution_lineage') IS NOT NULL", Boolean.class);
        if (present == null || !present) {
            LOGGER.warn("warehouse.institution_lineage is missing; apply crawlernest-schema/institution_lineage_postgresql.sql");
            return List.of();
        }
        String ids = canonicalUniversityIds.stream().map(String::valueOf).collect(Collectors.joining(",", "{", "}"));
        return jdbcTemplate.query("""
                SELECT predecessor_canonical_id, successor_canonical_id, effective_year, kind
                FROM warehouse.institution_lineage
                WHERE predecessor_canonical_id = ANY(?::bigint[])
                   OR successor_canonical_id = ANY(?::bigint[])
                ORDER BY effective_year, lineage_id
                """,
                (rs, rowNum) -> new InstitutionLineage.Event(
                        rs.getLong("predecessor_canonical_id"),
                        rs.getLong("successor_canonical_id"),
                        rs.getInt("effective_year"),
                        rs.getString("kind")),
                ids, ids);
    }
}
