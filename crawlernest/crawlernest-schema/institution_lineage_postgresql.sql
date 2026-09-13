-- =========================================================
-- Institution lineage: when two editions describe different institutions
-- =========================================================
--
-- Requires entity_resolution_postgresql.sql (warehouse.canonical_university).
--
-- A rank delta compares one university across two editions. That comparison is
-- only meaningful if the university is the same institution in both, and
-- mergers break it without changing anything the pipeline can see:
--
--   * Institute of Science Tokyo was formed on 2024-10-01 from Tokyo Institute of
--     Technology and Tokyo Medical and Dental University. The 2026 editions rank
--     "Institute of Science Tokyo"; the entity resolver attached those rows to the
--     existing Tokyo Tech record (canonical_slug
--     tokyo-institute-of-technology-tokyo-tech), and ARWU kept its old institution
--     slug. A 2025-to-2026 delta on that record would compare Tokyo Tech with a
--     merged institution twice its size, and no source-identity check notices.
--   * Adelaide University began on 2026-01-01 from The University of Adelaide and
--     the University of South Australia. Same shape: the 2026 rows sit on the
--     University of Adelaide record.
--
-- One row records one structural event. crawlernest/core/institution_lineage.py
-- and clawer.service.InstitutionLineage read it, and any comparison whose window
-- contains an event naming the university -- on either side -- is withheld with
-- reason entity_changed.
--
-- effective_year is the calendar year the change took effect, not an edition
-- label. Editions are labelled ahead of publication (QS and THE name an edition
-- a year after they publish it), so the readers widen the window by one year on
-- the prior side: withholding one comparison that was in fact sound is the safe
-- way to be wrong.
--
-- predecessor_canonical_id may equal successor_canonical_id. The warehouse holds
-- one record per name the resolver settled on, not per legal entity, and a merger
-- whose absorbed institution was never ingested -- or a rename -- has no second
-- record to point at. That row says "this record's institution changed here".
--
-- Additive and read-only for the pipeline: nothing writes it but this file and a
-- reviewer.

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

    CONSTRAINT ck_institution_lineage_date_matches_year CHECK (
        effective_date IS NULL OR EXTRACT(YEAR FROM effective_date)::INTEGER = effective_year
    ),
    CONSTRAINT uq_institution_lineage_event
        UNIQUE (predecessor_canonical_id, successor_canonical_id, effective_year, kind)
);

CREATE INDEX IF NOT EXISTS idx_institution_lineage_predecessor
    ON warehouse.institution_lineage(predecessor_canonical_id);

CREATE INDEX IF NOT EXISTS idx_institution_lineage_successor
    ON warehouse.institution_lineage(successor_canonical_id);

-- ---------------------------------------------------------
-- Known events
-- ---------------------------------------------------------
-- Looked up by canonical_slug, so a database that does not hold these
-- universities (a freshly bootstrapped CI database) inserts nothing, and a
-- re-run inserts nothing twice.

INSERT INTO warehouse.institution_lineage
    (predecessor_canonical_id, successor_canonical_id, effective_year, effective_date, kind, note, recorded_by)
SELECT predecessor.canonical_university_id,
       successor.canonical_university_id,
       event.effective_year,
       event.effective_date,
       event.kind,
       event.note,
       'institution_lineage_postgresql.sql'
FROM (
    VALUES
        ('tokyo-medical-and-dental-university-tmdu', 'tokyo-institute-of-technology-tokyo-tech',
         2024, DATE '2024-10-01', 'merger',
         'Institute of Science Tokyo formed from Tokyo Tech and TMDU. 2026 edition rows for Institute of Science Tokyo resolve to the Tokyo Tech record.'),
        ('university-of-south-australia', 'the-university-of-adelaide',
         2026, DATE '2026-01-01', 'merger',
         'Adelaide University formed from The University of Adelaide and the University of South Australia. 2026 edition rows for Adelaide University resolve to the University of Adelaide record.')
) AS event(predecessor_slug, successor_slug, effective_year, effective_date, kind, note)
JOIN warehouse.canonical_university predecessor ON predecessor.canonical_slug = event.predecessor_slug
JOIN warehouse.canonical_university successor ON successor.canonical_slug = event.successor_slug
ON CONFLICT ON CONSTRAINT uq_institution_lineage_event DO NOTHING;
