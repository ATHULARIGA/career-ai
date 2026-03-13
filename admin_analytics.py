import csv
import io
import json
import db_backend as db
import time
from datetime import datetime
from typing import Any, Dict, List

DB_PATH = "bookings.db"


def _conn():
    return db.get_conn()


def _repair_identity_sequence(conn, table: str) -> None:
    if not db.is_postgres():
        return
    cur = conn.cursor()
    cur.execute(
        """
        SELECT pg_get_serial_sequence(%s, 'id')
        """,
        (table,),
    )
    seq_row = cur.fetchone()
    if not seq_row or not seq_row[0]:
        return
    seq_name = seq_row[0]
    cur.execute(f'SELECT COALESCE(MAX(id), 0) + 1 FROM "{table}"')
    next_id = int(cur.fetchone()[0])
    cur.execute("SELECT setval(%s, %s, false)", (seq_name, next_id))


def init_admin_tables() -> None:
    conn = _conn()
    cur = conn.cursor()
    id_col = db.id_pk_col()

    db.execute(
        cur,
        f"""
        CREATE TABLE IF NOT EXISTS user_events(
            id {id_col},
            ts INTEGER,
            event_type TEXT,
            feature TEXT,
            user_id TEXT,
            cohort TEXT,
            region TEXT,
            role TEXT,
            metadata TEXT
        )
        """,
    )
    db.execute(cur, "CREATE INDEX IF NOT EXISTS idx_user_events_user_ts ON user_events(user_id, ts)")
    db.execute(cur, "CREATE INDEX IF NOT EXISTS idx_user_events_type_ts ON user_events(event_type, ts)")
    db.execute(
        cur,
        f"""
        CREATE TABLE IF NOT EXISTS model_health(
            id {id_col},
            ts INTEGER,
            feature TEXT,
            model_name TEXT,
            success INTEGER,
            latency_ms REAL,
            fallback_used INTEGER,
            error_message TEXT
        )
        """,
    )
    db.execute(
        cur,
        f"""
        CREATE TABLE IF NOT EXISTS feedback_queue(
            id {id_col},
            ts INTEGER,
            source TEXT,
            severity TEXT,
            message TEXT,
            status TEXT
        )
        """,
    )
    db.execute(
        cur,
        f"""
        CREATE TABLE IF NOT EXISTS audit_logs(
            id {id_col},
            ts INTEGER,
            actor TEXT,
            action TEXT,
            details TEXT
        )
        """,
    )
    db.execute(
        cur,
        f"""
        CREATE TABLE IF NOT EXISTS experiments(
            id {id_col},
            feature TEXT UNIQUE,
            prompt_version TEXT,
            model_name TEXT,
            enabled INTEGER,
            updated_ts INTEGER
        )
        """,
    )
    db.execute(
        cur,
        f"""
        CREATE TABLE IF NOT EXISTS ab_tests(
            id {id_col},
            experiment_name TEXT UNIQUE,
            variant_a TEXT,
            variant_b TEXT,
            winner TEXT,
            updated_ts INTEGER
        )
        """,
    )
    db.execute(
        cur,
        f"""
        CREATE TABLE IF NOT EXISTS safety_events(
            id {id_col},
            ts INTEGER,
            level TEXT,
            event_type TEXT,
            payload TEXT
        )
        """,
    )
    db.execute(
        cur,
        f"""
        CREATE TABLE IF NOT EXISTS mentor_ops(
            id {id_col},
            ts INTEGER,
            metric_name TEXT,
            metric_value REAL,
            note TEXT
        )
        """,
    )
    db.execute(cur, 
        """
        CREATE TABLE IF NOT EXISTS admin_settings(
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_ts INTEGER
        )
        """
    )
    for t in (
        "user_events",
        "model_health",
        "feedback_queue",
        "audit_logs",
        "experiments",
        "ab_tests",
        "safety_events",
        "mentor_ops",
    ):
        _repair_identity_sequence(conn, t)
    conn.commit()
    conn.close()


def _now() -> int:
    return int(time.time())


def log_event(
    event_type: str,
    feature: str,
    user_id: str = "anonymous",
    cohort: str = "general",
    region: str = "US",
    role: str = "",
    metadata: Dict[str, Any] = None,
) -> None:
    conn = _conn()
    try:
        cur = conn.cursor()
        db.execute(cur, 
            """
            INSERT INTO user_events(ts,event_type,feature,user_id,cohort,region,role,metadata)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                _now(),
                event_type,
                feature,
                user_id,
                cohort,
                region,
                role,
                json.dumps(metadata or {}),
            ),
        )
        conn.commit()
    except Exception:
        # Never fail user requests because analytics logging failed.
        conn.rollback()
    finally:
        conn.close()


def log_model_health(
    feature: str,
    model_name: str,
    success: bool,
    latency_ms: float,
    fallback_used: bool = False,
    error_message: str = "",
) -> None:
    conn = _conn()
    cur = conn.cursor()
    db.execute(cur, 
        """
        INSERT INTO model_health(ts,feature,model_name,success,latency_ms,fallback_used,error_message)
        VALUES (?,?,?,?,?,?,?)
        """,
        (
            _now(),
            feature,
            model_name,
            1 if success else 0,
            float(latency_ms),
            1 if fallback_used else 0,
            error_message[:300],
        ),
    )
    conn.commit()
    conn.close()


def add_feedback(source: str, severity: str, message: str, status: str = "open") -> None:
    conn = _conn()
    cur = conn.cursor()
    db.execute(cur, 
        """
        INSERT INTO feedback_queue(ts,source,severity,message,status)
        VALUES (?,?,?,?,?)
        """,
        (_now(), source, severity, message[:1000], status),
    )
    conn.commit()
    conn.close()


def update_feedback_status(feedback_id: int, status: str) -> None:
    conn = _conn()
    cur = conn.cursor()
    db.execute(cur, "UPDATE feedback_queue SET status=? WHERE id=?", (status, feedback_id))
    conn.commit()
    conn.close()


def log_audit(actor: str, action: str, details: str = "") -> None:
    conn = _conn()
    cur = conn.cursor()
    db.execute(cur, 
        """
        INSERT INTO audit_logs(ts,actor,action,details)
        VALUES (?,?,?,?)
        """,
        (_now(), actor, action, details[:1000]),
    )
    conn.commit()
    conn.close()


def upsert_experiment(feature: str, prompt_version: str, model_name: str, enabled: bool) -> None:
    conn = _conn()
    cur = conn.cursor()
    db.execute(cur, 
        """
        INSERT INTO experiments(feature,prompt_version,model_name,enabled,updated_ts)
        VALUES (?,?,?,?,?)
        ON CONFLICT(feature) DO UPDATE SET
            prompt_version=excluded.prompt_version,
            model_name=excluded.model_name,
            enabled=excluded.enabled,
            updated_ts=excluded.updated_ts
        """,
        (feature, prompt_version, model_name, 1 if enabled else 0, _now()),
    )
    conn.commit()
    conn.close()


def upsert_ab_test(experiment_name: str, variant_a: str, variant_b: str, winner: str) -> None:
    conn = _conn()
    cur = conn.cursor()
    db.execute(cur, 
        """
        INSERT INTO ab_tests(experiment_name,variant_a,variant_b,winner,updated_ts)
        VALUES (?,?,?,?,?)
        ON CONFLICT(experiment_name) DO UPDATE SET
            variant_a=excluded.variant_a,
            variant_b=excluded.variant_b,
            winner=excluded.winner,
            updated_ts=excluded.updated_ts
        """,
        (experiment_name, variant_a, variant_b, winner, _now()),
    )
    conn.commit()
    conn.close()


def add_safety_event(level: str, event_type: str, payload: str = "") -> None:
    conn = _conn()
    cur = conn.cursor()
    db.execute(cur, 
        """
        INSERT INTO safety_events(ts,level,event_type,payload)
        VALUES (?,?,?,?)
        """,
        (_now(), level, event_type, payload[:1000]),
    )
    conn.commit()
    conn.close()


def log_mentor_metric(metric_name: str, metric_value: float, note: str = "") -> None:
    conn = _conn()
    cur = conn.cursor()
    db.execute(cur, 
        """
        INSERT INTO mentor_ops(ts,metric_name,metric_value,note)
        VALUES (?,?,?,?)
        """,
        (_now(), metric_name, float(metric_value), note[:300]),
    )
    conn.commit()
    conn.close()


def _fetchall(query: str, params: tuple = ()) -> List[tuple]:
    conn = _conn()
    cur = conn.cursor()
    db.execute(cur, query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def _scalar(query: str, params: tuple = ()) -> int:
    rows = _fetchall(query, params)
    if not rows:
        return 0
    val = rows[0][0]
    return int(val or 0)


def dashboard_payload(bookings: List[tuple]) -> Dict[str, Any]:
    today_key = datetime.utcnow().strftime("%Y-%m-%d")

    total_bookings = len(bookings)
    unique_users = len(set([(b[2] or "").lower() for b in bookings]))
    today_bookings = len([b for b in bookings if today_key in str(b[4])])

    resume_reviews = _scalar("SELECT COUNT(*) FROM user_events WHERE event_type='resume_review_completed'")
    interview_started = _scalar("SELECT COUNT(*) FROM user_events WHERE event_type='interview_started'")
    interview_completed = _scalar("SELECT COUNT(*) FROM user_events WHERE event_type='interview_completed'")
    roadmap_generated = _scalar("SELECT COUNT(*) FROM user_events WHERE event_type='roadmap_generated'")
    mentor_bookings = _scalar("SELECT COUNT(*) FROM user_events WHERE event_type='mentor_booking_created'")

    conversion = {
        "resume_reviews": resume_reviews,
        "interview_started": interview_started,
        "interview_completed": interview_completed,
        "mentor_bookings": mentor_bookings,
    }

    model_rows = _fetchall(
        """
        SELECT feature, model_name, success, latency_ms, fallback_used, error_message
        FROM model_health ORDER BY ts DESC LIMIT 50
        """
    )
    success_count = len([r for r in model_rows if r[2] == 1])
    success_rate = round((success_count / max(1, len(model_rows))) * 100, 1)
    avg_latency = round(sum([float(r[3] or 0) for r in model_rows]) / max(1, len(model_rows)), 1)
    fallback_rate = round((len([r for r in model_rows if r[4] == 1]) / max(1, len(model_rows))) * 100, 1)

    feedback = _fetchall("SELECT id, ts, source, severity, message, status FROM feedback_queue ORDER BY ts DESC LIMIT 50")
    safety = _fetchall("SELECT id, ts, level, event_type, payload FROM safety_events ORDER BY ts DESC LIMIT 30")
    experiments = _fetchall("SELECT feature, prompt_version, model_name, enabled, updated_ts FROM experiments ORDER BY feature")
    ab_tests = _fetchall("SELECT experiment_name, variant_a, variant_b, winner, updated_ts FROM ab_tests ORDER BY experiment_name")
    audit = _fetchall("SELECT ts, actor, action, details FROM audit_logs ORDER BY ts DESC LIMIT 60")

    cohorts = _fetchall(
        """
        SELECT cohort, COUNT(*) FROM user_events
        WHERE event_type='resume_review_completed'
        GROUP BY cohort ORDER BY COUNT(*) DESC
        """
    )

    mentor_rows = _fetchall(
        """
        SELECT metric_name, metric_value, note, ts FROM mentor_ops
        ORDER BY ts DESC LIMIT 20
        """
    )
    mentor_index = {}
    for m in mentor_rows:
        if m[0] not in mentor_index:
            mentor_index[m[0]] = {"value": m[1], "note": m[2], "ts": m[3]}

    mentor_default = {
        "calendar_load_pct": {"value": 0, "note": "No data", "ts": 0},
        "no_show_rate_pct": {"value": 0, "note": "No data", "ts": 0},
        "mentor_quality_score": {"value": 0, "note": "No data", "ts": 0},
        "reschedule_rate_pct": {"value": 0, "note": "No data", "ts": 0},
    }
    mentor_default.update(mentor_index)

    return {
        "kpis": {
            "total_bookings": total_bookings,
            "unique_users": unique_users,
            "today_bookings": today_bookings,
            "resume_reviews": resume_reviews,
            "interview_completed": interview_completed,
            "roadmap_generated": roadmap_generated,
        },
        "conversion": conversion,
        "model_health": {
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency,
            "fallback_rate": fallback_rate,
            "recent": model_rows,
        },
        "feedback_queue": feedback,
        "safety_events": safety,
        "experiments": experiments,
        "ab_tests": ab_tests,
        "audit_logs": audit,
        "cohorts": cohorts,
        "mentor_ops": mentor_default,
        "bookings": bookings,
    }


def export_all_json(bookings: List[tuple]) -> str:
    payload = dashboard_payload(bookings)
    return json.dumps(payload, indent=2)


def export_all_csv(bookings: List[tuple]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["booking_id", "name", "email", "topic", "datetime", "link"])
    for b in bookings:
        writer.writerow(list(b))
    writer.writerow([])
    writer.writerow(["event_type", "count"])
    rows = _fetchall("SELECT event_type, COUNT(*) FROM user_events GROUP BY event_type ORDER BY COUNT(*) DESC")
    for r in rows:
        writer.writerow([r[0], r[1]])
    return out.getvalue()


def set_setting(key: str, value: str) -> None:
    conn = _conn()
    cur = conn.cursor()
    db.execute(cur, 
        """
        INSERT INTO admin_settings(key,value,updated_ts)
        VALUES (?,?,?)
        ON CONFLICT(key) DO UPDATE SET
            value=excluded.value,
            updated_ts=excluded.updated_ts
        """,
        (key, value, _now()),
    )
    conn.commit()
    conn.close()


def get_setting(key: str, default: str = "") -> str:
    rows = _fetchall("SELECT value FROM admin_settings WHERE key=?", (key,))
    if not rows:
        return default
    return str(rows[0][0] or default)
