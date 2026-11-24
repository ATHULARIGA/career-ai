"""
Canonical schema management and index optimization for CareerAI.
Provides centralized table initialization and performance indexing
across PostgreSQL (production) and SQLite (testing).
"""

import logging
import db.backend as db

logger = logging.getLogger("resumate")


def ensure_performance_indexes(conn) -> None:
    """Creates essential performance indexes for foreign key lookups and sorting."""
    cur = conn.cursor()
    indexes = [
        # User lookups
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
        # Resume history lookups
        "CREATE INDEX IF NOT EXISTS idx_saved_resumes_user_ts ON saved_resumes(user_email, updated_ts DESC)",
        "CREATE INDEX IF NOT EXISTS idx_resume_reports_user_ts ON resume_reports(user_email, created_ts DESC)",
        # Interview history lookups
        "CREATE INDEX IF NOT EXISTS idx_interview_sessions_user_ts ON interview_sessions(user_email, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_user_cheatsheets ON user_cheatsheets(user_email, tech_name)",
        # Booking lookups
        "CREATE INDEX IF NOT EXISTS idx_bookings_email ON bookings(email)",
        "CREATE INDEX IF NOT EXISTS idx_bookings_mentor ON bookings(mentor_email)",
        # Monetization & upgrade requests
        "CREATE INDEX IF NOT EXISTS idx_premium_requests_user ON premium_requests(user_email, status)",
        # Coding submissions and timeline
        "CREATE INDEX IF NOT EXISTS idx_coding_submissions_user_created ON coding_submissions(user_email, created_ts)",
        "CREATE INDEX IF NOT EXISTS idx_coding_submissions_user_status ON coding_submissions(user_email, status)",
        "CREATE INDEX IF NOT EXISTS idx_timeline_user_ts ON coding_attempt_timeline(user_email, created_ts)",
        "CREATE INDEX IF NOT EXISTS idx_timeline_user_problem_ts ON coding_attempt_timeline(user_email, problem_id, created_ts)",
        "CREATE INDEX IF NOT EXISTS idx_timeline_problem_hash ON coding_attempt_timeline(problem_id, code_hash)",
        # Telemetry & events
        "CREATE INDEX IF NOT EXISTS idx_user_events_user_ts ON user_events(user_id, ts)",
        "CREATE INDEX IF NOT EXISTS idx_user_events_type_ts ON user_events(event_type, ts)",
    ]

    for sql in indexes:
        try:
            db.execute(cur, sql)
        except Exception as exc:
            logger.debug("Index ensure skipped: %s (%s)", sql, exc)

    conn.commit()


def init_all_schemas(run_seed: bool = True) -> None:
    """Initializes all domain tables, ensures columns, and applies performance indexes."""
    try:
        from services.analytics.admin_analytics import init_admin_tables
        from services.coding.coding_platform import init_coding_tables
        from services.booking.booking_db import init_booking_tables
        from core.database import (
            init_user_tables,
            _ensure_auth_tables,
            init_resume_tables,
            _ensure_interview_tables,
            seed_default_sample_resume,
        )

        init_admin_tables()
        init_coding_tables()
        init_user_tables()
        _ensure_auth_tables()
        init_resume_tables()
        _ensure_interview_tables()
        init_booking_tables()

        if run_seed:
            seed_default_sample_resume()

        # Apply performance indexes
        conn = db.get_conn()
        try:
            ensure_performance_indexes(conn)
        finally:
            conn.close()

    except Exception as exc:
        logger.warning("Database schema check deferred or skipped: %s", exc)
