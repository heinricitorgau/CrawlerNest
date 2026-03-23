-- Archived legacy SQLite experimental schema retained only for migration reference.
CREATE TABLE IF NOT EXISTS universities_tmp (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rank_value TEXT,
    name TEXT,
    country TEXT,
    path TEXT,
    overall_score TEXT,
    academic_reputation TEXT,
    employer_reputation TEXT
);
