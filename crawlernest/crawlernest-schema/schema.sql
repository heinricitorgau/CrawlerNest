PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

DROP TABLE IF EXISTS field_status_logs;
DROP TABLE IF EXISTS tuition;
DROP TABLE IF EXISTS admission_requirements;
DROP TABLE IF EXISTS degrees;
DROP TABLE IF EXISTS programs;
DROP TABLE IF EXISTS rankings;
DROP TABLE IF EXISTS raw_source_records;
DROP TABLE IF EXISTS university_aliases;
DROP TABLE IF EXISTS universities;
DROP TABLE IF EXISTS countries;
DROP TABLE IF EXISTS crawl_runs;

-- =========================================================
-- Warehouse control / lineage
-- =========================================================

CREATE TABLE crawl_runs (
    crawl_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    ranking_type TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    status TEXT DEFAULT 'running',
    notes TEXT
);

-- =========================================================
-- Dimensions
-- =========================================================

CREATE TABLE countries (
    country_id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT UNIQUE,
    country_name TEXT NOT NULL UNIQUE,
    region_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE universities (
    university_id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_slug TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    canonical_name TEXT,
    country_id INTEGER,
    city_name TEXT,
    website_url TEXT,
    qs_profile_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (country_id) REFERENCES countries(country_id)
);

CREATE TABLE university_aliases (
    alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
    university_id INTEGER NOT NULL,
    source_name TEXT NOT NULL,
    source_school_name TEXT NOT NULL,
    match_type TEXT DEFAULT 'manual',
    confidence_score REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (university_id) REFERENCES universities(university_id),
    UNIQUE(source_name, source_school_name)
);

CREATE TABLE programs (
    program_id INTEGER PRIMARY KEY AUTOINCREMENT,
    university_id INTEGER NOT NULL,
    program_name TEXT NOT NULL,
    canonical_program_name TEXT,
    program_category TEXT,
    department_name TEXT,
    study_field TEXT,
    source_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (university_id) REFERENCES universities(university_id),
    UNIQUE(university_id, program_name)
);

CREATE TABLE degrees (
    degree_id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id INTEGER NOT NULL,
    degree_name TEXT NOT NULL,
    degree_level TEXT,
    duration_text TEXT,
    delivery_mode TEXT,
    source_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (program_id) REFERENCES programs(program_id),
    UNIQUE(program_id, degree_name, degree_level)
);

-- =========================================================
-- Raw / staging layer
-- =========================================================

CREATE TABLE raw_source_records (
    raw_id INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_run_id INTEGER,
    source_name TEXT NOT NULL,
    record_type TEXT,
    ranking_type TEXT,
    source_url TEXT,
    raw_json TEXT,
    raw_text TEXT,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (crawl_run_id) REFERENCES crawl_runs(crawl_run_id)
);

-- =========================================================
-- Fact tables
-- =========================================================

CREATE TABLE rankings (
    ranking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    university_id INTEGER NOT NULL,
    raw_id INTEGER,
    ranking_source TEXT NOT NULL,
    ranking_type TEXT NOT NULL,
    ranking_year INTEGER,
    rank_start INTEGER,
    rank_end INTEGER,
    score REAL,
    metrics_json TEXT,
    source_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (university_id) REFERENCES universities(university_id),
    FOREIGN KEY (raw_id) REFERENCES raw_source_records(raw_id),
    CHECK (rank_start IS NULL OR rank_start > 0),
    CHECK (rank_end IS NULL OR rank_end > 0),
    CHECK (score IS NULL OR score >= 0)
);

CREATE TABLE admission_requirements (
    requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    university_id INTEGER NOT NULL,
    program_id INTEGER,
    degree_id INTEGER,
    raw_id INTEGER,
    source_url TEXT,
    gpa_min REAL,
    ielts_min REAL,
    toefl_min REAL,
    gre_min REAL,
    gmat_min REAL,
    application_deadline_text TEXT,
    raw_text TEXT,
    parsed_status TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (university_id) REFERENCES universities(university_id),
    FOREIGN KEY (program_id) REFERENCES programs(program_id),
    FOREIGN KEY (degree_id) REFERENCES degrees(degree_id),
    FOREIGN KEY (raw_id) REFERENCES raw_source_records(raw_id),
    CHECK (gpa_min IS NULL OR gpa_min >= 0),
    CHECK (ielts_min IS NULL OR ielts_min >= 0),
    CHECK (toefl_min IS NULL OR toefl_min >= 0),
    CHECK (gre_min IS NULL OR gre_min >= 0),
    CHECK (gmat_min IS NULL OR gmat_min >= 0)
);

CREATE TABLE tuition (
    tuition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    university_id INTEGER NOT NULL,
    program_id INTEGER,
    degree_id INTEGER,
    raw_id INTEGER,
    tuition_amount REAL,
    currency_code TEXT,
    tuition_period TEXT,
    raw_text TEXT,
    source_url TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (university_id) REFERENCES universities(university_id),
    FOREIGN KEY (program_id) REFERENCES programs(program_id),
    FOREIGN KEY (degree_id) REFERENCES degrees(degree_id),
    FOREIGN KEY (raw_id) REFERENCES raw_source_records(raw_id),
    CHECK (tuition_amount IS NULL OR tuition_amount >= 0)
);

-- =========================================================
-- Data quality / parsing logs
-- =========================================================

CREATE TABLE field_status_logs (
    status_id INTEGER PRIMARY KEY AUTOINCREMENT,
    university_id INTEGER,
    raw_id INTEGER,
    field_name TEXT,
    field_raw_value TEXT,
    field_normalized_value TEXT,
    field_status TEXT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (university_id) REFERENCES universities(university_id),
    FOREIGN KEY (raw_id) REFERENCES raw_source_records(raw_id)
);

-- =========================================================
-- Indexes
-- =========================================================

CREATE INDEX idx_countries_name ON countries(country_name);
CREATE INDEX idx_universities_slug ON universities(school_slug);
CREATE INDEX idx_universities_country ON universities(country_id);
CREATE INDEX idx_university_aliases_source_name ON university_aliases(source_name, source_school_name);
CREATE INDEX idx_raw_source_records_source_type ON raw_source_records(source_name, ranking_type);
CREATE INDEX idx_raw_source_records_crawl_run ON raw_source_records(crawl_run_id);
CREATE INDEX idx_rankings_university_year ON rankings(university_id, ranking_year);
CREATE INDEX idx_rankings_source_type ON rankings(ranking_source, ranking_type);
CREATE INDEX idx_rankings_raw ON rankings(raw_id);
CREATE INDEX idx_programs_university ON programs(university_id);
CREATE INDEX idx_degrees_program ON degrees(program_id);
CREATE INDEX idx_admission_requirements_university ON admission_requirements(university_id);
CREATE INDEX idx_admission_requirements_program ON admission_requirements(program_id);
CREATE INDEX idx_admission_requirements_degree ON admission_requirements(degree_id);
CREATE INDEX idx_tuition_university ON tuition(university_id);
CREATE INDEX idx_tuition_program ON tuition(program_id);
CREATE INDEX idx_tuition_degree ON tuition(degree_id);
CREATE INDEX idx_field_status_logs_raw ON field_status_logs(raw_id);
CREATE INDEX idx_field_status_logs_university ON field_status_logs(university_id);

COMMIT;