import time
import json
import logging
import os
import hashlib
import hmac
import secrets
from db import backend as db
from fastapi import Request
from features.shared import parse_json_object

logger = logging.getLogger("resumate")

def get_conn():
    return db.get_conn()

def execute(cur, query, params=None):
    return db.execute(cur, query, params)

def get_admin_settings() -> tuple:
    import os
    from dotenv import load_dotenv
    load_dotenv(override=True)
    admin_username = (os.getenv("ADMIN_USERNAME") or "").strip()
    admin_password = os.getenv("ADMIN_PASSWORD") or ""
    admin_email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
    return admin_username, admin_password, admin_email

def is_admin_session(request: Request) -> bool:
    return request.session.get("admin") is True

def current_user_plan(request: Request) -> str:
    if is_admin_session(request):
        return "premium"
    cached = (request.session.get("user_plan") or "").strip().lower()
    if cached in ("free", "premium"):
        return cached
    plan = user_plan_for_email(request.session.get("user_email", ""))
    request.session["user_plan"] = plan
    return plan

def is_premium_user(request: Request) -> bool:
    return current_user_plan(request) == "premium"

def _ensure_interview_tables():
    conn = db.get_conn()
    cur = conn.cursor()
    id_col = db.id_pk_col()
    db.execute(cur, f"""
        CREATE TABLE IF NOT EXISTS interview_sessions(
            id {id_col},
            session_id TEXT UNIQUE NOT NULL,
            user_email TEXT NOT NULL,
            topic TEXT,
            difficulty TEXT,
            overall_score REAL,
            qa_history_json TEXT,
            chat_history_json TEXT,
            created_at INTEGER
        )
    """)
    try:
        db.execute(cur, "ALTER TABLE interview_sessions ADD COLUMN chat_history_json TEXT")
    except Exception:
        pass
    conn.commit()
    conn.close()

def _ensure_auth_tables() -> None:
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, 
        """
        CREATE TABLE IF NOT EXISTS auth_rate_limits(
            rate_key TEXT PRIMARY KEY,
            window_start INTEGER NOT NULL,
            attempts INTEGER NOT NULL,
            blocked_until INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

def init_resume_tables() -> None:
    conn = db.get_conn()
    cur = conn.cursor()
    id_col = db.id_pk_col()
    db.execute(cur, 
        f"""
        CREATE TABLE IF NOT EXISTS resume_reports(
            id {id_col},
            user_email TEXT NOT NULL,
            target_role TEXT,
            overall REAL,
            ats REAL,
            keyword_coverage REAL,
            status TEXT,
            report_json TEXT NOT NULL,
            created_ts INTEGER NOT NULL
        )
        """
    )
    db.execute(cur, "CREATE INDEX IF NOT EXISTS idx_resume_reports_user_ts ON resume_reports(user_email, created_ts DESC)")
    if db.is_postgres():
        cur.execute("SELECT pg_get_serial_sequence('resume_reports', 'id')")
        seq_row = cur.fetchone()
        if seq_row and seq_row[0]:
            seq_name = seq_row[0]
            cur.execute('SELECT COALESCE(MAX(id), 0) + 1 FROM "resume_reports"')
            next_id = int(cur.fetchone()[0])
            cur.execute("SELECT setval(%s, %s, false)", (seq_name, next_id))
    conn.commit()
    conn.close()

def save_resume_report_for_user(user_email: str, report: dict, target_role: str = "") -> None:
    email = (user_email or "").strip().lower()
    if not email:
        return
    scores = report.get("scores", {}) if isinstance(report, dict) else {}
    conn = db.get_conn()
    cur = conn.cursor()
    params = (
        email,
        target_role or "",
        float(scores.get("Overall", 0) or 0),
        float(scores.get("ATS", 0) or 0),
        float(report.get("keyword_coverage", 0) or 0),
        str(scores.get("Status", "") or ""),
        json.dumps(report),
        int(time.time()),
    )
    query = """
        INSERT INTO resume_reports(
            user_email,target_role,overall,ats,keyword_coverage,status,report_json,created_ts
        ) VALUES(?,?,?,?,?,?,?,?)
    """
    try:
        db.execute(cur, query, params)
        conn.commit()
    except Exception:
        conn.rollback()
        if db.is_postgres():
            try:
                cur.execute("SELECT pg_get_serial_sequence('resume_reports', 'id')")
                seq_row = cur.fetchone()
                if seq_row and seq_row[0]:
                    seq_name = seq_row[0]
                    cur.execute('SELECT COALESCE(MAX(id), 0) + 1 FROM "resume_reports"')
                    next_id = int(cur.fetchone()[0])
                    cur.execute("SELECT setval(%s, %s, false)", (seq_name, next_id))
                db.execute(cur, query, params)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        else:
            raise
    finally:
        conn.close()

def get_latest_resume_report_for_user(user_email: str):
    email = (user_email or "").strip().lower()
    if not email:
        return None
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, 
        "SELECT report_json FROM resume_reports WHERE user_email=? ORDER BY created_ts DESC, id DESC LIMIT 1",
        (email,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    try:
        return json.loads(row[0] or "{}")
    except Exception:
        return None

def get_recent_resume_runs_for_user(user_email: str, limit: int = 10):
    email = (user_email or "").strip().lower()
    if not email:
        return []
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, 
        """
        SELECT id, created_ts, overall, ats, keyword_coverage, status, target_role
        FROM resume_reports
        WHERE user_email=?
        ORDER BY created_ts ASC, id ASC
        LIMIT ?
        """,
        (email, max(1, int(limit))),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": int(r[0] or 0),
            "timestamp": int(r[1] or 0),
            "overall": float(r[2] or 0),
            "ats": float(r[3] or 0),
            "keyword_coverage": float(r[4] or 0),
            "status": str(r[5] or ""),
            "target_role": str(r[6] or ""),
        }
        for r in rows
    ]

def get_resume_report_by_id_for_user(report_id: int, user_email: str):
    email = (user_email or "").strip().lower()
    if not email:
        return None
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, 
        "SELECT report_json, target_role FROM resume_reports WHERE id=? AND user_email=?",
        (int(report_id), email),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    try:
        report = json.loads(row[0] or "{}")
        if isinstance(report, dict):
            report["target_role"] = str(row[1] or "")
        return report
    except Exception:
        return None

def update_resume_report_json(report_id: int, user_email: str, updated_json: dict) -> bool:
    email = (user_email or "").strip().lower()
    if not email:
        return False
    conn = db.get_conn()
    cur = conn.cursor()
    try:
        db.execute(cur, 
            "UPDATE resume_reports SET report_json=? WHERE id=? AND user_email=?",
            (json.dumps(updated_json), int(report_id), email)
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update report_json for {report_id}: {e}")
        return False
    finally:
        conn.close()

def _auth_key(request, action: str, identity: str = "") -> str:
    ip = ""
    try:
        ip = request.client.host if request.client else ""
    except Exception:
        ip = ""
    return f"{action}:{(identity or '').strip().lower()}:{ip}"

def is_rate_limited(request, action: str, identity: str = "", max_attempts: int = 5, window_sec: int = 300, block_sec: int = 600):
    now = int(time.time())
    key = _auth_key(request, action, identity)
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, "SELECT window_start, attempts, blocked_until FROM auth_rate_limits WHERE rate_key=?", (key,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, 0
    window_start, attempts, blocked_until = int(row[0]), int(row[1]), int(row[2])
    if blocked_until > now:
        conn.close()
        return True, blocked_until - now
    if now - window_start > window_sec:
        db.execute(cur, "DELETE FROM auth_rate_limits WHERE rate_key=?", (key,))
        conn.commit()
        conn.close()
        return False, 0
    if attempts >= max_attempts:
        db.execute(cur, 
            "UPDATE auth_rate_limits SET blocked_until=? WHERE rate_key=?",
            (now + block_sec, key),
        )
        conn.commit()
        conn.close()
        return True, block_sec
    conn.close()
    return False, 0

def record_auth_failure(request, action: str, identity: str = "", window_sec: int = 300):
    now = int(time.time())
    key = _auth_key(request, action, identity)
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, "SELECT window_start, attempts FROM auth_rate_limits WHERE rate_key=?", (key,))
    row = cur.fetchone()
    if not row:
        db.execute(cur, 
            "INSERT INTO auth_rate_limits(rate_key, window_start, attempts, blocked_until) VALUES(?,?,?,?)",
            (key, now, 1, 0),
        )
    else:
        window_start, attempts = int(row[0]), int(row[1])
        if now - window_start > window_sec:
            db.execute(cur, 
                "UPDATE auth_rate_limits SET window_start=?, attempts=?, blocked_until=0 WHERE rate_key=?",
                (now, 1, key),
            )
        else:
            db.execute(cur, 
                "UPDATE auth_rate_limits SET attempts=?, blocked_until=blocked_until WHERE rate_key=?",
                (attempts + 1, key),
            )
    conn.commit()
    conn.close()

def record_auth_success(request, action: str, identity: str = ""):
    key = _auth_key(request, action, identity)
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, "DELETE FROM auth_rate_limits WHERE rate_key=?", (key,))
    conn.commit()
    conn.close()

def init_user_tables() -> None:
    conn = db.get_conn()
    cur = conn.cursor()
    id_col = db.id_pk_col()
    db.execute(cur, 
        f"""
        CREATE TABLE IF NOT EXISTS users(
            id {id_col},
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            plan TEXT NOT NULL DEFAULT 'free',
            premium_since INTEGER NOT NULL DEFAULT 0,
            premium_expires_ts INTEGER NOT NULL DEFAULT 0,
            reset_token TEXT,
            reset_token_expiry INTEGER NOT NULL DEFAULT 0,
            password_updated_ts INTEGER NOT NULL DEFAULT 0,
            created_ts INTEGER NOT NULL
        )
        """
    )
    cols = db.list_columns(conn, "users")
    if "role" not in cols:
        db.execute(cur, "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    if "reset_token" not in cols:
        db.execute(cur, "ALTER TABLE users ADD COLUMN reset_token TEXT")
    if "reset_token_expiry" not in cols:
        db.execute(cur, "ALTER TABLE users ADD COLUMN reset_token_expiry INTEGER NOT NULL DEFAULT 0")
    if "password_updated_ts" not in cols:
        db.execute(cur, "ALTER TABLE users ADD COLUMN password_updated_ts INTEGER NOT NULL DEFAULT 0")
    if "plan" not in cols:
        db.execute(cur, "ALTER TABLE users ADD COLUMN plan TEXT NOT NULL DEFAULT 'free'")
    if "premium_since" not in cols:
        db.execute(cur, "ALTER TABLE users ADD COLUMN premium_since INTEGER NOT NULL DEFAULT 0")
    if "premium_expires_ts" not in cols:
        db.execute(cur, "ALTER TABLE users ADD COLUMN premium_expires_ts INTEGER NOT NULL DEFAULT 0")
    db.execute(cur, "UPDATE users SET plan='free' WHERE plan IS NULL OR TRIM(plan)=''")
    db.execute(cur, "UPDATE users SET premium_since=0 WHERE premium_since IS NULL")
    db.execute(cur, "UPDATE users SET premium_expires_ts=0 WHERE premium_expires_ts IS NULL")
    db.execute(
        cur,
        f"""
        CREATE TABLE IF NOT EXISTS premium_requests(
            id {id_col},
            user_id INTEGER,
            user_email TEXT NOT NULL,
            upi_txn_ref TEXT NOT NULL,
            amount TEXT,
            screenshot_url TEXT,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            rejection_reason TEXT,
            created_ts INTEGER NOT NULL,
            reviewed_ts INTEGER NOT NULL DEFAULT 0,
            reviewed_by TEXT
        )
        """,
    )
    db.execute(
        cur,
        f"""
        CREATE TABLE IF NOT EXISTS user_memory(
            id {id_col},
            user_email TEXT UNIQUE NOT NULL,
            target_role TEXT,
            target_company TEXT,
            focus_area TEXT,
            updated_ts INTEGER NOT NULL
        )
        """,
    )
    conn.commit()
    conn.close()

def user_plan_for_email(user_email: str) -> str:
    email = (user_email or "").strip().lower()
    if not email:
        return "free"
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, "SELECT plan FROM users WHERE email=?", (email,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return "free"
    plan = str((row[0] or "free")).strip().lower()
    return plan if plan else "free"

def get_user_memory(user_email: str, conn=None) -> dict:
    email = (user_email or "").strip().lower()
    if not email:
        return {"target_role": "", "target_company": "", "focus_area": ""}
    close_after = False
    if conn is None:
        conn = db.get_conn()
        close_after = True
    cur = conn.cursor()
    try:
        db.execute(
            cur,
            "SELECT target_role,target_company,focus_area FROM user_memory WHERE user_email=?",
            (email,),
        )
        row = cur.fetchone()
    finally:
        if close_after:
            conn.close()
    if not row:
        return {"target_role": "", "target_company": "", "focus_area": ""}
    return {
        "target_role": str(row[0] or ""),
        "target_company": str(row[1] or ""),
        "focus_area": str(row[2] or ""),
    }


def validate_password_strength(password: str) -> str:
    if len(password or "") < 8:
        return "Password must be at least 8 characters."
    if not any(c.islower() for c in password):
        return "Password must include a lowercase letter."
    if not any(c.isupper() for c in password):
        return "Password must include an uppercase letter."
    if not any(c.isdigit() for c in password):
        return "Password must include a number."
    return ""

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        (password or "").encode("utf-8"),
        salt.encode("utf-8"),
        200_000,
    ).hex()
    return f"pbkdf2_sha256$200000${salt}${digest}"

def verify_password(stored: str, password: str) -> bool:
    value = (stored or "").strip()
    if value.startswith("pbkdf2_sha256$"):
        try:
            _, rounds, salt, digest = value.split("$", 3)
            current = hashlib.pbkdf2_hmac(
                "sha256",
                (password or "").encode("utf-8"),
                salt.encode("utf-8"),
                int(rounds),
            ).hex()
            return hmac.compare_digest(current, digest)
        except Exception:
            return False
    legacy = hashlib.sha256((password or "").encode("utf-8")).hexdigest()
    return hmac.compare_digest(value, legacy)

def save_user_memory(user_email: str, target_role: str, target_company: str, focus_area: str) -> None:
    email = (user_email or "").strip().lower()
    if not email:
        return
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(
        cur,
        """
        INSERT INTO user_memory(user_email,target_role,target_company,focus_area,updated_ts)
        VALUES(?,?,?,?,?)
        ON CONFLICT(user_email) DO UPDATE SET
            target_role=excluded.target_role,
            target_company=excluded.target_company,
            focus_area=excluded.focus_area,
            updated_ts=excluded.updated_ts
        """,
        (email, (target_role or "").strip()[:120], (target_company or "").strip()[:120], (focus_area or "").strip()[:120], int(time.time())),
    )
    conn.commit()
    conn.close()

def _ensure_interview_tables():
    conn = db.get_conn()
    cur = conn.cursor()
    id_col = db.id_pk_col()
    db.execute(cur, f"""
        CREATE TABLE IF NOT EXISTS interview_sessions(
            id {id_col},
            session_id TEXT UNIQUE NOT NULL,
            user_email TEXT NOT NULL,
            topic TEXT,
            difficulty TEXT,
            overall_score REAL,
            qa_history_json TEXT,
            chat_history_json TEXT,
            created_at INTEGER
        )
    """)
    try:
        db.execute(cur, "ALTER TABLE interview_sessions ADD COLUMN chat_history_json TEXT")
    except Exception:
        pass
    conn.commit()
    conn.close()

def _solved_problem_count(user_email: str) -> int:
    email = (user_email or "").strip().lower()
    if not email:
        return 0
    try:
        conn = db.get_conn()
        cur = conn.cursor()
        db.execute(
            cur,
            """
            SELECT COUNT(DISTINCT problem_id)
            FROM coding_submissions
            WHERE user_email=? AND mode='submit' AND status='Accepted'
            """,
            (email,),
        )
        row = cur.fetchone() or (0,)
        conn.close()
        return int(row[0] or 0)
    except Exception:
        return 0

def get_user_weaknesses(user_email: str) -> list[str]:
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, "SELECT qa_history_json FROM interview_sessions WHERE user_email=?", (user_email,))
    rows = cur.fetchall()
    weaknesses = set()
    for row in rows:
        try:
            hist = json.loads(row[0])
            for item in hist:
                if item.get("score", 10) < 6.0:
                    fb = item.get("feedback")
                    if fb:
                        weaknesses.add(fb[:100] + "...")
        except Exception:
            pass
    conn.close()
    return list(weaknesses)[:3]

def user_progress_summary(user_email: str, conn=None) -> dict:
    from features.coding.platform import submission_ts_column
    empty_progress = {
        "resume_runs_7d": 0,
        "resume_avg_7d": 0.0,
        "coding_submissions_7d": 0,
        "coding_accept_rate_7d": 0.0,
        "active_days_7d": 0,
        "current_streak_days": 0,
        "next_action": "Run your first resume review (8 min).",
    }
    email = (user_email or "").strip().lower()
    if not email:
        return dict(empty_progress)
    now_ts = int(time.time())
    seven_days_ago = now_ts - (7 * 24 * 60 * 60)
    thirty_days_ago = now_ts - (30 * 24 * 60 * 60)
    close_after = False
    if conn is None:
        conn = db.get_conn()
        close_after = True
    try:
        cur = conn.cursor()
        db.execute(
            cur,
            "SELECT COUNT(*), COALESCE(AVG(overall),0) FROM resume_reports WHERE user_email=? AND created_ts>=?",
            (email, seven_days_ago),
        )
        resume_row = cur.fetchone() or (0, 0)
        coding_ts_col = submission_ts_column(conn)
        if coding_ts_col:
            db.execute(
                cur,
                f"SELECT COUNT(*), COALESCE(AVG(CASE WHEN status='Accepted' THEN 100.0 ELSE 0 END),0) FROM coding_submissions WHERE user_email=? AND {coding_ts_col}>=?",
                (email, seven_days_ago),
            )
            coding_row = cur.fetchone() or (0, 0)
        else:
            coding_row = (0, 0)
        db.execute(
            cur,
            "SELECT created_ts FROM resume_reports WHERE user_email=? AND created_ts>=?",
            (email, thirty_days_ago),
        )
        resume_days_rows = cur.fetchall() or []
        if coding_ts_col:
            db.execute(
                cur,
                f"SELECT {coding_ts_col} FROM coding_submissions WHERE user_email=? AND {coding_ts_col}>=?",
                (email, thirty_days_ago),
            )
            coding_days_rows = cur.fetchall() or []
        else:
            coding_days_rows = []
        
        # User events
        try:
            db.execute(
                cur,
                "SELECT ts FROM user_events WHERE user_id=? AND ts>=?",
                (email, thirty_days_ago),
            )
            events_days_rows = cur.fetchall() or []
        except Exception:
            events_days_rows = []
            
    except Exception as progress_error:
        logger.warning("progress_summary_failed user=%s err=%s", email, str(progress_error))
        return dict(empty_progress)
    finally:
        if close_after:
            conn.close()

    resume_runs = int(resume_row[0] or 0)
    resume_avg = round(float(resume_row[1] or 0), 1)
    coding_subs = int(coding_row[0] or 0)
    coding_accept = round(float(coding_row[1] or 0), 1)
    active_days = set()
    for row in resume_days_rows:
        try:
            ts = int(row[0] or 0)
            if ts > 0:
                active_days.add(time.strftime("%Y-%m-%d", time.localtime(ts)))
        except Exception:
            continue
    for row in coding_days_rows:
        try:
            ts = int(row[0] or 0)
            if ts > 0:
                active_days.add(time.strftime("%Y-%m-%d", time.localtime(ts)))
        except Exception:
            continue
    for row in events_days_rows:
        try:
            ts = int(row[0] or 0)
            if ts > 0:
                active_days.add(time.strftime("%Y-%m-%d", time.localtime(ts)))
        except Exception:
            continue

    active_days_7d = 0
    current_streak_days = 0
    day_cursor = now_ts
    for _ in range(7):
        day_key = time.strftime("%Y-%m-%d", time.localtime(day_cursor))
        if day_key in active_days:
            active_days_7d += 1
        day_cursor -= 24 * 60 * 60

    day_cursor = now_ts
    for _ in range(31):
        day_key = time.strftime("%Y-%m-%d", time.localtime(day_cursor))
        if day_key in active_days:
            current_streak_days += 1
            day_cursor -= 24 * 60 * 60
            continue
        break

    if resume_runs == 0:
        next_action = "Run one resume review for your target role (8 min)."
    elif coding_subs < 3:
        next_action = "Submit one coding problem to improve interview readiness (12 min)."
    elif coding_accept < 60:
        next_action = "Practice one Easy coding problem and focus on edge cases (12 min)."
    else:
        next_action = "Run a 3-round mock interview and apply one improvement point (10 min)."

    return {
        "resume_runs_7d": resume_runs,
        "resume_avg_7d": resume_avg,
        "coding_submissions_7d": coding_subs,
        "coding_accept_rate_7d": coding_accept,
        "active_days_7d": active_days_7d,
        "current_streak_days": current_streak_days,
        "next_action": next_action,
    }

def safe_user_progress_summary(user_email: str) -> dict:
    try:
        return user_progress_summary(user_email)
    except Exception as progress_error:
        logger.warning("safe_progress_summary_failed user=%s err=%s", (user_email or "").strip().lower(), str(progress_error))
        return {
            "resume_runs_7d": 0,
            "resume_avg_7d": 0.0,
            "coding_submissions_7d": 0,
            "coding_accept_rate_7d": 0.0,
            "active_days_7d": 0,
            "current_streak_days": 0,
            "next_action": "Run your first resume review (8 min).",
        }
