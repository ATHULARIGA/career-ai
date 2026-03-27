import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from db import backend as db
from features.coding import platform as coding_platform
import main


def _set_temp_sqlite(tmp_path: Path) -> Path:
    db_path = tmp_path / "compat.db"
    db.DATABASE_URL = ""
    db.SQLITE_PATH = str(db_path)
    db._USE_SQLITE_FALLBACK = True
    coding_platform.reset_submission_ts_cache()
    return db_path


def _create_base_tables(db_path: Path, submission_cols_sql: str) -> None:
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS resume_reports(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            target_role TEXT,
            overall REAL,
            ats REAL,
            keyword_coverage REAL,
            status TEXT,
            report_json TEXT,
            created_ts INTEGER
        )
        """
    )
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS coding_submissions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem_id TEXT,
            language TEXT,
            mode TEXT,
            status TEXT,
            passed INTEGER,
            total INTEGER,
            runtime_ms REAL,
            user_email TEXT,
            {submission_cols_sql}
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER,
            event_type TEXT,
            feature TEXT,
            user_id TEXT,
            cohort TEXT,
            region TEXT,
            role TEXT,
            metadata TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def test_user_progress_summary_with_created_ts(tmp_path):
    db_path = _set_temp_sqlite(tmp_path)
    _create_base_tables(db_path, "created_ts INTEGER")
    now = 2_000_000_000
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO coding_submissions(problem_id,language,mode,status,passed,total,runtime_ms,user_email,created_ts) VALUES(?,?,?,?,?,?,?,?,?)",
        ("p1", "python", "submit", "Accepted", 1, 1, 10.0, "u@example.com", now),
    )
    conn.commit()
    conn.close()

    original_time = main.time.time
    main.time.time = lambda: now
    try:
        out = main.user_progress_summary("u@example.com")
    finally:
        main.time.time = original_time
    assert out["coding_submissions_7d"] == 1
    assert out["coding_accept_rate_7d"] == 100.0


def test_user_progress_summary_with_legacy_ts(tmp_path):
    db_path = _set_temp_sqlite(tmp_path)
    _create_base_tables(db_path, "ts INTEGER")
    now = 2_000_000_100
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO coding_submissions(problem_id,language,mode,status,passed,total,runtime_ms,user_email,ts) VALUES(?,?,?,?,?,?,?,?,?)",
        ("p1", "python", "submit", "Accepted", 1, 1, 10.0, "u@example.com", now),
    )
    conn.commit()
    conn.close()
    coding_platform.reset_submission_ts_cache()

    original_time = main.time.time
    main.time.time = lambda: now
    try:
        out = main.user_progress_summary("u@example.com")
    finally:
        main.time.time = original_time
    assert out["coding_submissions_7d"] == 1
    assert out["coding_accept_rate_7d"] == 100.0


def test_user_progress_summary_prefers_created_ts_when_both(tmp_path):
    db_path = _set_temp_sqlite(tmp_path)
    _create_base_tables(db_path, "created_ts INTEGER, ts INTEGER")
    now = 2_000_000_200
    old = now - (40 * 24 * 60 * 60)
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO coding_submissions(problem_id,language,mode,status,passed,total,runtime_ms,user_email,created_ts,ts) VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("p1", "python", "submit", "Accepted", 1, 1, 10.0, "u@example.com", old, now),
    )
    conn.commit()
    conn.close()
    coding_platform.reset_submission_ts_cache()

    original_time = main.time.time
    main.time.time = lambda: now
    try:
        out = main.user_progress_summary("u@example.com")
    finally:
        main.time.time = original_time
    assert out["coding_submissions_7d"] == 0


def test_user_progress_summary_with_missing_timestamp_cols(tmp_path):
    db_path = _set_temp_sqlite(tmp_path)
    _create_base_tables(db_path, "note TEXT")
    coding_platform.reset_submission_ts_cache()
    out = main.user_progress_summary("u@example.com")
    assert out["coding_submissions_7d"] == 0
    assert out["coding_accept_rate_7d"] == 0.0


def test_account_route_renders_when_coding_timestamp_missing(tmp_path):
    db_path = _set_temp_sqlite(tmp_path)
    _create_base_tables(db_path, "note TEXT")
    main.init_user_tables()
    main._ensure_auth_tables()
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE email=?", ("u@example.com",))
    cur.execute(
        "INSERT INTO users(full_name,email,password_hash,role,plan,password_updated_ts,created_ts) VALUES(?,?,?,?,?,?,?)",
        ("User", "u@example.com", main.hash_password("Passw0rdA"), "user", "free", 2_000_000_000, 2_000_000_000),
    )
    conn.commit()
    conn.close()
    coding_platform.reset_submission_ts_cache()

    client = TestClient(main.app)
    login_resp = client.post(
        "/login",
        data={"email": "u@example.com", "password": "Passw0rdA", "website": ""},
        follow_redirects=False,
    )
    assert login_resp.status_code in (302, 303)
    resp = client.get("/account")
    assert resp.status_code == 200
    assert "Account Settings" in resp.text
