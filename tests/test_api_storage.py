# coding: utf-8

import sqlite3


def test_job_store_migrates_existing_database_with_consent_columns(tmp_path):
    from src.api.storage import JobStore

    db_path = tmp_path / "jobs.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                source_filename TEXT NOT NULL,
                driving_filename TEXT NOT NULL,
                source_path TEXT NOT NULL,
                driving_path TEXT NOT NULL,
                output_dir TEXT NOT NULL,
                result_path TEXT,
                error_message TEXT,
                source_sha256 TEXT NOT NULL,
                driving_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    JobStore(db_path)

    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}

    assert "consent_confirmed" in columns
    assert "usage_policy_version" in columns
