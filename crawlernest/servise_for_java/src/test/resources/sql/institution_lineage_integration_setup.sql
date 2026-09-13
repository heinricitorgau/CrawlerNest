-- The table from crawlernest-schema/institution_lineage_postgresql.sql, without its
-- seeded events. api-tests.yml runs `mvnw test` against a bare PostgreSQL, so each
-- integration test creates what it reads, as rankings_integration_setup.sql does.

CREATE TABLE IF NOT EXISTS warehouse.institution_lineage (
    lineage_id BIGSERIAL PRIMARY KEY,
    predecessor_canonical_id BIGINT NOT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    successor_canonical_id BIGINT NOT NULL
        REFERENCES warehouse.canonical_university(canonical_university_id),
    effective_year INTEGER NOT NULL
        CHECK (effective_year BETWEEN 1800 AND 2200),
    effective_date DATE,
    kind TEXT NOT NULL
        CHECK (kind IN ('merger', 'split', 'rename')),
    note TEXT,
    recorded_by TEXT NOT NULL DEFAULT 'schema',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_institution_lineage_event
        UNIQUE (predecessor_canonical_id, successor_canonical_id, effective_year, kind)
);

-- MIT (990002) merged into ETH Zurich (990001), effective 2100: the fixture's
-- stand-in for Tokyo Tech and TMDU.
INSERT INTO warehouse.institution_lineage
    (predecessor_canonical_id, successor_canonical_id, effective_year, kind, note, recorded_by)
VALUES (990002, 990001, 2100, 'merger', 'integration test fixture', 'integration_test')
ON CONFLICT ON CONSTRAINT uq_institution_lineage_event DO NOTHING;
