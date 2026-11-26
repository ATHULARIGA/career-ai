import csv
import io
import json
import threading
import time
from datetime import datetime, timedelta
from typing import Any

import db.backend as db

DB_PATH = "bookings.db"
_last_dashboard_cache: dict[str, Any] = {"ts": 0, "payload": None}


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
    allowed_tables = {
        "admin_events", "admin_model_health", "admin_feedback", "admin_audits",
        "admin_experiments", "admin_ab_tests", "admin_safety_events", "admin_mentor_metrics",
        "user_events", "model_health", "feedback_queue", "audit_logs",
        "experiments", "ab_tests", "safety_events", "mentor_ops", "visitor_traffic"
    }
    if table not in allowed_tables:
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
    db.execute(
        cur,
        f"""
        CREATE TABLE IF NOT EXISTS visitor_traffic(
            id {id_col},
            ts INTEGER,
            ip TEXT,
            country TEXT,
            region TEXT,
            city TEXT,
            path TEXT,
            method TEXT,
            status_code INTEGER,
            user_agent TEXT,
            user_id TEXT
        )
        """,
    )
    db.execute(cur, "CREATE INDEX IF NOT EXISTS idx_visitor_traffic_ts ON visitor_traffic(ts)")
    db.execute(cur, "CREATE INDEX IF NOT EXISTS idx_visitor_traffic_ip ON visitor_traffic(ip)")
    db.execute(cur, "CREATE INDEX IF NOT EXISTS idx_visitor_traffic_country ON visitor_traffic(country)")
    for t in (
        "user_events",
        "model_health",
        "feedback_queue",
        "audit_logs",
        "experiments",
        "ab_tests",
        "safety_events",
        "mentor_ops",
        "visitor_traffic",
    ):
        _repair_identity_sequence(conn, t)
    conn.commit()
    conn.close()


def _now() -> int:
    return int(time.time())


def _async_log_event(
    event_type: str,
    feature: str,
    user_id: str,
    cohort: str,
    region: str,
    role: str,
    metadata_json: str,
) -> None:
    try:
        conn = _conn()
        try:
            cur = conn.cursor()
            db.execute(
                cur,
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
                    metadata_json,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def log_event(
    event_type: str,
    feature: str,
    user_id: str = "anonymous",
    cohort: str = "general",
    region: str = "US",
    role: str = "",
    metadata: dict[str, Any] = None,
) -> None:
    meta_str = json.dumps(metadata or {})
    # In pytest/test runs, execute synchronously so test assertions work deterministically
    if db.is_testing():
        _async_log_event(event_type, feature, user_id, cohort, region, role, meta_str)
        return

    # In production/runtime, execute asynchronously in a background daemon thread so the HTTP response is instantaneous
    threading.Thread(
        target=_async_log_event,
        args=(event_type, feature, user_id, cohort, region, role, meta_str),
        daemon=True,
    ).start()


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


def _fetchall(query: str, params: tuple = ()) -> list[tuple]:
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


def dashboard_payload(bookings: list[tuple]) -> dict[str, Any]:
    now = time.time()
    # In production, cache the analytics payload for 15 seconds to make sub-navigation instantaneous
    if not db.is_testing() and _last_dashboard_cache["payload"] and (now - _last_dashboard_cache["ts"]) < 15:
        cached = dict(_last_dashboard_cache["payload"])
        cached["bookings"] = bookings
        return cached

    today_key = datetime.utcnow().strftime("%Y-%m-%d")

    total_bookings = len(bookings)
    unique_users = len(set([(b[2] or "").lower() for b in bookings]))
    today_bookings = len([b for b in bookings if today_key in str(b[4])])

    conn = _conn()
    cur = conn.cursor()
    try:
        # 1. Consolidated user_events metrics
        db.execute(cur, "SELECT event_type, COUNT(*) FROM user_events GROUP BY event_type")
        ev_counts = dict(cur.fetchall())
        resume_reviews = ev_counts.get("resume_review_completed", 0)
        interview_started = ev_counts.get("interview_started", 0)
        interview_completed = ev_counts.get("interview_completed", 0)
        roadmap_generated = ev_counts.get("roadmap_generated", 0)
        mentor_bookings = ev_counts.get("mentor_booking_created", 0)

        # 2. Consolidated user roles and plans
        db.execute(cur, "SELECT role, plan, COUNT(*) FROM users GROUP BY role, plan")
        user_rows = cur.fetchall()
        total_registered_users = sum(r[2] for r in user_rows)
        admin_users_count = sum(r[2] for r in user_rows if r[0] == "admin")
        mentor_users_count = sum(r[2] for r in user_rows if r[0] == "mentor")
        regular_users_count = sum(r[2] for r in user_rows if r[0] in ("user", None, ""))
        premium_users_count = sum(r[2] for r in user_rows if r[1] in ("pro", "premium", "enterprise"))

        # 3. Coding submissions
        db.execute(cur, "SELECT COUNT(*) FROM coding_submissions")
        c_row = cur.fetchone()
        coding_submissions_count = int(c_row[0] or 0) if c_row else 0

        conversion = {
            "resume_reviews": resume_reviews,
            "interview_started": interview_started,
            "interview_completed": interview_completed,
            "mentor_bookings": mentor_bookings,
        }

        # Conversion ratios
        conv_rates = {
            "resume_to_interview": round((interview_started / max(1, resume_reviews)) * 100, 1),
            "interview_complete_rate": round((interview_completed / max(1, interview_started)) * 100, 1),
            "interview_to_mentor": round((mentor_bookings / max(1, interview_completed)) * 100, 1),
            "user_to_mentor": round((total_bookings / max(1, total_registered_users)) * 100, 1),
        }
        conv_classes = {
            k: f"w-pct-{min(100, max(0, round(v / 5) * 5))}"
            for k, v in conv_rates.items()
        }

        # Tool engagement distribution
        total_actions = max(1, resume_reviews + interview_completed + roadmap_generated + coding_submissions_count + total_bookings)
        tool_share = {
            "resume": round((resume_reviews / total_actions) * 100, 1),
            "interview": round((interview_completed / total_actions) * 100, 1),
            "roadmap": round((roadmap_generated / total_actions) * 100, 1),
            "coding": round((coding_submissions_count / total_actions) * 100, 1),
            "mentorship": round((total_bookings / total_actions) * 100, 1),
        }
        tool_classes = {
            k: f"w-pct-{min(100, max(0, round(v / 5) * 5))}"
            for k, v in tool_share.items()
        }

        # User tier breakdown
        free_users_count = max(0, total_registered_users - premium_users_count)
        user_tier_share = {
            "free": round((free_users_count / max(1, total_registered_users)) * 100, 1),
            "pro": round((premium_users_count / max(1, total_registered_users)) * 100, 1),
            "admin": round((admin_users_count / max(1, total_registered_users)) * 100, 1),
        }
        user_tier_classes = {
            k: f"w-pct-{min(100, max(0, round(v / 5) * 5))}"
            for k, v in user_tier_share.items()
        }

        # 7-day daily activity trends
        now_ts = int(time.time())
        seven_days_ago = now_ts - (7 * 86400)
        day_series = []
        day_map = {}
        for i in range(6, -1, -1):
            d_str = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
            d_label = (datetime.utcnow() - timedelta(days=i)).strftime("%b %d")
            day_series.append(d_str)
            day_map[d_str] = {
                "date": d_str,
                "label": d_label,
                "events": 0,
                "resumes": 0,
                "interviews": 0,
                "signups": 0,
                "bar_pct": 8,
                "bar_class": "h-pct-10",
            }

        try:
            db.execute(cur, "SELECT ts, event_type FROM user_events WHERE ts >= ?", (seven_days_ago,))
            recent_events = cur.fetchall()
            for ev_ts, ev_type in recent_events:
                d_key = datetime.utcfromtimestamp(int(ev_ts or 0)).strftime("%Y-%m-%d")
                if d_key in day_map:
                    day_map[d_key]["events"] += 1
                    if ev_type == "resume_review_completed":
                        day_map[d_key]["resumes"] += 1
                    elif ev_type in ("interview_started", "interview_completed"):
                        day_map[d_key]["interviews"] += 1

            db.execute(cur, "SELECT created_ts FROM users WHERE created_ts >= ?", (seven_days_ago,))
            recent_users = cur.fetchall()
            for (u_ts,) in recent_users:
                d_key = datetime.utcfromtimestamp(int(u_ts or 0)).strftime("%Y-%m-%d")
                if d_key in day_map:
                    day_map[d_key]["signups"] += 1

            activity_trend = [day_map[d] for d in day_series]
            max_day_events = max(1, max([d["events"] for d in activity_trend]))
            for d in activity_trend:
                pct = min(100, max(8, int((d["events"] / max_day_events) * 100)))
                d["bar_pct"] = pct
                pct_cls = min(100, max(10, round(pct / 5) * 5))
                d["bar_class"] = f"h-pct-{pct_cls}"
        except Exception:
            activity_trend = [day_map[d] for d in day_series]

        db.execute(
            cur,
            """
            SELECT feature, model_name, success, latency_ms, fallback_used, error_message
            FROM model_health ORDER BY ts DESC LIMIT 50
            """,
        )
        model_rows = cur.fetchall()
        success_count = len([r for r in model_rows if r[2] == 1])
        success_rate = round((success_count / max(1, len(model_rows))) * 100, 1)
        avg_latency = round(sum([float(r[3] or 0) for r in model_rows]) / max(1, len(model_rows)), 1)
        fallback_rate = round((len([r for r in model_rows if r[4] == 1]) / max(1, len(model_rows))) * 100, 1)

        db.execute(cur, "SELECT id, ts, source, severity, message, status FROM feedback_queue ORDER BY ts DESC LIMIT 50")
        feedback = cur.fetchall()
        db.execute(cur, "SELECT id, ts, level, event_type, payload FROM safety_events ORDER BY ts DESC LIMIT 30")
        safety = cur.fetchall()
        db.execute(cur, "SELECT feature, prompt_version, model_name, enabled, updated_ts FROM experiments ORDER BY feature")
        experiments = cur.fetchall()
        db.execute(cur, "SELECT experiment_name, variant_a, variant_b, winner, updated_ts FROM ab_tests ORDER BY experiment_name")
        ab_tests = cur.fetchall()
        db.execute(cur, "SELECT ts, actor, action, details FROM audit_logs ORDER BY ts DESC LIMIT 60")
        audit = cur.fetchall()

        db.execute(
            cur,
            """
            SELECT cohort, COUNT(*) FROM user_events
            WHERE event_type='resume_review_completed'
            GROUP BY cohort ORDER BY COUNT(*) DESC
            """,
        )
        cohorts = cur.fetchall()

        db.execute(
            cur,
            """
            SELECT metric_name, metric_value, note, ts FROM mentor_ops
            ORDER BY ts DESC LIMIT 20
            """,
        )
        mentor_rows = cur.fetchall()
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
    finally:
        conn.close()

    result = {
        "kpis": {
            "total_bookings": total_bookings,
            "unique_users": unique_users,
            "today_bookings": today_bookings,
            "resume_reviews": resume_reviews,
            "interview_completed": interview_completed,
            "roadmap_generated": roadmap_generated,
            "total_users": total_registered_users,
            "admin_users": admin_users_count,
            "pro_users": premium_users_count,
            "coding_submissions": coding_submissions_count,
        },
        "user_stats": {
            "total": total_registered_users,
            "admins": admin_users_count,
            "mentors": mentor_users_count,
            "regular": regular_users_count,
            "premium": premium_users_count,
            "free": max(0, total_registered_users - premium_users_count),
        },
        "conversion": conversion,
        "conv_rates": conv_rates,
        "conv_classes": conv_classes,
        "tool_share": tool_share,
        "tool_classes": tool_classes,
        "user_tier_share": user_tier_share,
        "user_tier_classes": user_tier_classes,
        "activity_trend": activity_trend,
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
    _last_dashboard_cache["ts"] = now
    _last_dashboard_cache["payload"] = result
    return result


def get_admin_users_list(search: str = "", role_filter: str = "", limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    """Retrieves registered users for the admin user management interface."""
    query = "SELECT id, full_name, email, role, plan, created_ts, premium_since, premium_expires_ts FROM users WHERE 1=1"
    params = []
    if search:
        s = f"%{search.strip().lower()}%"
        query += " AND (LOWER(email) LIKE ? OR LOWER(full_name) LIKE ?)"
        params.extend([s, s])
    if role_filter and role_filter in ("admin", "user", "mentor"):
        query += " AND role = ?"
        params.append(role_filter)
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = _fetchall(query, tuple(params))
    users = []
    for r in rows:
        created_dt = datetime.utcfromtimestamp(int(r[5] or 0)).strftime("%Y-%m-%d %H:%M") if r[5] else "N/A"
        users.append({
            "id": r[0],
            "full_name": r[1] or "Unknown",
            "email": r[2] or "",
            "role": r[3] or "user",
            "plan": r[4] or "free",
            "created_ts": r[5] or 0,
            "created_date": created_dt,
            "premium_since": r[6] or 0,
            "premium_expires_ts": r[7] or 0,
        })
    return users


def update_user_role(user_id: int, new_role: str, actor: str) -> tuple[bool, str]:
    """Promotes or demotes a user's role and logs an audit trail event."""
    if new_role not in ("admin", "user", "mentor"):
        return False, "Invalid role specified."

    conn = _conn()
    cur = conn.cursor()
    db.execute(cur, "SELECT id, email, role FROM users WHERE id = ?", (user_id,))
    target = cur.fetchone()
    if not target:
        conn.close()
        return False, "User not found."

    old_role = target[2] or "user"
    target_email = target[1]

    db.execute(cur, "UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    conn.commit()
    conn.close()

    log_audit(actor, "user_role_change", f"user_id={user_id},email={target_email},old_role={old_role},new_role={new_role}")
    return True, f"Successfully updated role of {target_email} from {old_role} to {new_role}."


def export_all_json(bookings: list[tuple]) -> str:
    payload = dashboard_payload(bookings)
    return json.dumps(payload, indent=2)


def export_all_csv(bookings: list[tuple]) -> str:
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


def get_periodic_report(period: str = "daily") -> dict[str, Any]:
    """Generates time-aggregated metrics partitioned by daily, monthly, or yearly intervals."""
    period = (period or "daily").lower().strip()
    if period not in ("daily", "monthly", "yearly"):
        period = "daily"

    now_dt = datetime.utcnow()
    intervals = []
    interval_map = {}

    if period == "daily":
        # 14-day rolling window
        for i in range(13, -1, -1):
            day_dt = now_dt - timedelta(days=i)
            key = day_dt.strftime("%Y-%m-%d")
            label = day_dt.strftime("%b %d")
            intervals.append(key)
            interval_map[key] = {
                "key": key,
                "label": label,
                "signups": 0,
                "resumes": 0,
                "interviews": 0,
                "bookings": 0,
                "coding": 0,
                "events": 0,
                "bar_pct": 5,
                "bar_class": "h-pct-5",
            }
        min_ts = int((now_dt - timedelta(days=14)).timestamp())
        fmt_key = "%Y-%m-%d"

    elif period == "monthly":
        # 12-month rolling window
        year = now_dt.year
        month = now_dt.month
        for i in range(11, -1, -1):
            m = month - i
            y = year
            while m <= 0:
                m += 12
                y -= 1
            key = f"{y:04d}-{m:02d}"
            label = datetime(y, m, 1).strftime("%b %Y")
            intervals.append(key)
            interval_map[key] = {
                "key": key,
                "label": label,
                "signups": 0,
                "resumes": 0,
                "interviews": 0,
                "bookings": 0,
                "coding": 0,
                "events": 0,
                "bar_pct": 5,
                "bar_class": "h-pct-5",
            }
        earliest_month = intervals[0]
        ey, em = map(int, earliest_month.split("-"))
        min_ts = int(datetime(ey, em, 1).timestamp())
        fmt_key = "%Y-%m"

    else:
        # Yearly window (last 5 calendar years)
        current_year = now_dt.year
        for y in range(current_year - 4, current_year + 1):
            key = str(y)
            intervals.append(key)
            interval_map[key] = {
                "key": key,
                "label": str(y),
                "signups": 0,
                "resumes": 0,
                "interviews": 0,
                "bookings": 0,
                "coding": 0,
                "events": 0,
                "bar_pct": 5,
                "bar_class": "h-pct-5",
            }
        min_ts = int(datetime(current_year - 4, 1, 1).timestamp())
        fmt_key = "%Y"

    conn = _conn()
    cur = conn.cursor()
    try:
        # 1. user_events aggregation
        db.execute(cur, "SELECT ts, event_type FROM user_events WHERE ts >= ?", (min_ts,))
        for ts, ev_type in cur.fetchall():
            k = datetime.utcfromtimestamp(int(ts or 0)).strftime(fmt_key)
            if k in interval_map:
                interval_map[k]["events"] += 1
                if ev_type == "resume_review_completed":
                    interval_map[k]["resumes"] += 1
                elif ev_type in ("interview_started", "interview_completed"):
                    interval_map[k]["interviews"] += 1
                elif ev_type == "mentor_booking_created":
                    interval_map[k]["bookings"] += 1

        # 2. users (signups)
        db.execute(cur, "SELECT created_ts FROM users WHERE created_ts >= ?", (min_ts,))
        for (u_ts,) in cur.fetchall():
            k = datetime.utcfromtimestamp(int(u_ts or 0)).strftime(fmt_key)
            if k in interval_map:
                interval_map[k]["signups"] += 1

        # 3. coding_submissions
        try:
            db.execute(cur, "SELECT ts FROM coding_submissions WHERE ts >= ?", (min_ts,))
            for (c_ts,) in cur.fetchall():
                k = datetime.utcfromtimestamp(int(c_ts or 0)).strftime(fmt_key)
                if k in interval_map:
                    interval_map[k]["coding"] += 1
        except Exception:
            pass
    finally:
        conn.close()

    series = [interval_map[k] for k in intervals]
    max_events = max(1, max([s["events"] + s["signups"] + s["coding"] for s in series]))
    for s in series:
        activity_sum = s["events"] + s["signups"] + s["coding"]
        pct = min(100, max(5, int((activity_sum / max_events) * 100)))
        s["bar_pct"] = pct
        pct_cls = min(100, max(5, round(pct / 5) * 5))
        s["bar_class"] = f"h-pct-{pct_cls}"

    totals = {
        "signups": sum(s["signups"] for s in series),
        "resumes": sum(s["resumes"] for s in series),
        "interviews": sum(s["interviews"] for s in series),
        "bookings": sum(s["bookings"] for s in series),
        "coding": sum(s["coding"] for s in series),
        "events": sum(s["events"] for s in series),
    }

    return {
        "period": period,
        "title": f"{period.capitalize()} Performance Report",
        "intervals": series,
        "totals": totals,
    }


def export_periodic_report_csv(period: str = "daily") -> str:
    """Exports structured periodic report as formatted CSV."""
    report = get_periodic_report(period)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Period Interval", "New Signups", "Resume Audits", "Mock Interviews", "Mentorship Bookings", "Coding Practice", "Total Platform Events"])
    for row in report["intervals"]:
        writer.writerow([
            row["label"],
            row["signups"],
            row["resumes"],
            row["interviews"],
            row["bookings"],
            row["coding"],
            row["events"],
        ])
    writer.writerow([])
    writer.writerow([
        "TOTAL",
        report["totals"]["signups"],
        report["totals"]["resumes"],
        report["totals"]["interviews"],
        report["totals"]["bookings"],
        report["totals"]["coding"],
        report["totals"]["events"],
    ])
    return out.getvalue()


def export_periodic_report_json(period: str = "daily") -> str:
    """Exports structured periodic report as formatted JSON."""
    report = get_periodic_report(period)
    return json.dumps(report, indent=2)


def _async_record_traffic(
    ip: str,
    country: str,
    region: str,
    city: str,
    path: str,
    method: str,
    status_code: int,
    user_agent: str,
    user_id: str,
) -> None:
    try:
        conn = _conn()
        try:
            cur = conn.cursor()
            db.execute(
                cur,
                """
                INSERT INTO visitor_traffic(ts, ip, country, region, city, path, method, status_code, user_agent, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _now(),
                    (ip or "unknown")[:64],
                    (country or "Unknown")[:64],
                    (region or "Unknown")[:64],
                    (city or "Unknown")[:128],
                    (path or "/")[:255],
                    (method or "GET")[:10],
                    int(status_code or 200),
                    (user_agent or "")[:255],
                    (user_id or "anonymous")[:64],
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass


def record_visitor_traffic(
    ip: str,
    country: str = "Unknown",
    region: str = "Unknown",
    city: str = "Unknown",
    path: str = "/",
    method: str = "GET",
    status_code: int = 200,
    user_agent: str = "",
    user_id: str = "anonymous",
) -> None:
    """
    Log client request traffic asynchronously with real IP and geographic metadata.
    """
    if db.is_testing():
        _async_record_traffic(ip, country, region, city, path, method, status_code, user_agent, user_id)
        return

    t = threading.Thread(
        target=_async_record_traffic,
        args=(ip, country, region, city, path, method, status_code, user_agent, user_id),
        daemon=True,
    )
    t.start()


_visitor_analytics_cache: dict[str, Any] = {}


def get_visitor_traffic_analytics(search_ip: str = "", limit: int = 50) -> dict[str, Any]:
    """
    Aggregates visitor traffic, unique visitor IPs, top countries/cities, and granular access log.
    """
    now = _now()
    cache_key = f"{search_ip}:{limit}"
    if not db.is_testing() and cache_key in _visitor_analytics_cache and (now - _visitor_analytics_cache[cache_key]["ts"] < 10):
        return _visitor_analytics_cache[cache_key]["data"]

    conn = _conn()
    cur = conn.cursor()
    day_ago = now - 86400
    week_ago = now - 7 * 86400
    month_ago = now - 30 * 86400

    # 1. Consolidated count metrics in a single round-trip query
    db.execute(
        cur,
        """
        SELECT
            COUNT(*),
            COUNT(DISTINCT ip),
            COUNT(DISTINCT CASE WHEN ts >= ? THEN ip ELSE NULL END),
            COUNT(DISTINCT CASE WHEN ts >= ? THEN ip ELSE NULL END),
            COUNT(DISTINCT CASE WHEN ts >= ? THEN ip ELSE NULL END),
            COUNT(DISTINCT CASE WHEN country NOT IN ('Unknown', '') THEN country ELSE NULL END)
        FROM visitor_traffic
        """,
        (day_ago, week_ago, month_ago),
    )
    row = cur.fetchone() or (0, 0, 0, 0, 0, 0)
    total_hits = int(row[0] or 0)
    unique_ips_total = int(row[1] or 0)
    unique_ips_today = int(row[2] or 0)
    unique_ips_week = int(row[3] or 0)
    unique_ips_month = int(row[4] or 0)
    unique_countries = int(row[5] or 0)

    # 6. Top Countries
    db.execute(
        cur,
        """
        SELECT country, COUNT(DISTINCT ip) as unique_ips, COUNT(*) as hits
        FROM visitor_traffic
        WHERE country NOT IN ('Unknown', '')
        GROUP BY country
        ORDER BY unique_ips DESC, hits DESC
        LIMIT 10
        """,
    )
    top_countries = [
        {"country": r[0], "unique_ips": int(r[1]), "hits": int(r[2])}
        for r in cur.fetchall()
    ]

    # 7. Top Cities
    db.execute(
        cur,
        """
        SELECT city, country, COUNT(DISTINCT ip) as unique_ips, COUNT(*) as hits
        FROM visitor_traffic
        WHERE city NOT IN ('Unknown', '')
        GROUP BY city, country
        ORDER BY unique_ips DESC, hits DESC
        LIMIT 10
        """,
    )
    top_cities = [
        {"city": r[0], "country": r[1], "unique_ips": int(r[2]), "hits": int(r[3])}
        for r in cur.fetchall()
    ]

    # 8. Top Visited Pages
    db.execute(
        cur,
        """
        SELECT path, COUNT(DISTINCT ip) as unique_ips, COUNT(*) as hits
        FROM visitor_traffic
        GROUP BY path
        ORDER BY hits DESC, unique_ips DESC
        LIMIT 10
        """,
    )
    top_paths = [
        {"path": r[0], "unique_ips": int(r[1]), "hits": int(r[2])}
        for r in cur.fetchall()
    ]

    # 9. Recent Visitor Access Log
    query = """
        SELECT ts, ip, country, region, city, path, method, status_code, user_agent, user_id
        FROM visitor_traffic
    """
    params = []
    if (search_ip or "").strip():
        query += " WHERE ip LIKE ? OR country LIKE ? OR city LIKE ? OR path LIKE ?"
        like_p = f"%{search_ip.strip()}%"
        params.extend([like_p, like_p, like_p, like_p])
    query += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)

    db.execute(cur, query, tuple(params))
    recent_visitors = []
    for r in cur.fetchall():
        import datetime
        dt_str = datetime.datetime.fromtimestamp(int(r[0]), tz=datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        recent_visitors.append({
            "ts": int(r[0]),
            "ts_str": dt_str,
            "ip": r[1],
            "country": r[2] or "Unknown",
            "region": r[3] or "Unknown",
            "city": r[4] or "Unknown",
            "path": r[5] or "/",
            "method": r[6] or "GET",
            "status_code": int(r[7] or 200),
            "user_agent": r[8] or "",
            "user_id": r[9] or "anonymous",
        })

    conn.close()

    result = {
        "kpis": {
            "total_hits": total_hits,
            "unique_ips_total": unique_ips_total,
            "unique_ips_today": unique_ips_today,
            "unique_ips_week": unique_ips_week,
            "unique_ips_month": unique_ips_month,
            "unique_countries": unique_countries,
        },
        "top_countries": top_countries,
        "top_cities": top_cities,
        "top_paths": top_paths,
        "recent_visitors": recent_visitors,
        "search_query": search_ip,
    }
    _visitor_analytics_cache[cache_key] = {"ts": now, "data": result}
    return result


def export_visitor_traffic_csv(limit: int = 1000) -> str:
    """Exports raw visitor traffic access log to CSV format."""
    conn = _conn()
    cur = conn.cursor()
    db.execute(
        cur,
        """
        SELECT ts, ip, country, region, city, path, method, status_code, user_agent, user_id
        FROM visitor_traffic
        ORDER BY ts DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    import csv
    import datetime
    import io

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Timestamp_UTC", "IP", "Country", "Region", "City", "Path", "Method", "Status_Code", "User_Agent", "User_ID"])
    for r in rows:
        dt_str = datetime.datetime.fromtimestamp(int(r[0]), tz=datetime.UTC).strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([dt_str, r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9]])
    return out.getvalue()


def export_visitor_traffic_json(limit: int = 1000) -> str:
    """Exports raw visitor traffic access log to JSON format."""
    conn = _conn()
    cur = conn.cursor()
    db.execute(
        cur,
        """
        SELECT ts, ip, country, region, city, path, method, status_code, user_agent, user_id
        FROM visitor_traffic
        ORDER BY ts DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    import datetime
    import json

    records = []
    for r in rows:
        dt_str = datetime.datetime.fromtimestamp(int(r[0]), tz=datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        records.append({
            "timestamp": dt_str,
            "ts": int(r[0]),
            "ip": r[1],
            "country": r[2],
            "region": r[3],
            "city": r[4],
            "path": r[5],
            "method": r[6],
            "status_code": int(r[7]),
            "user_agent": r[8],
            "user_id": r[9],
        })
    return json.dumps(records, indent=2)
