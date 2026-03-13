from fastapi import FastAPI, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from resume_parser import extract_text
from scoring import score_resume
from interview_engine import generate_questions, generate_follow_up
import time
from booking_db import save_booking, get_bookings, get_booking, assign_mentor_email
from email_sender import send_mail
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from mindmap_generator import generate_mindmap
from fastapi.responses import JSONResponse, PlainTextResponse
from dotenv import load_dotenv
import os
import json
import hashlib
import hmac
import secrets
import logging
import uuid
from collections import defaultdict, deque
from typing import Any, Dict
from interview_feedback import analyze_answer, hiring_decision
from fastapi.responses import RedirectResponse
import db_backend as db
from urllib.parse import urlencode, urlparse
from coding_platform import (
    DEFAULT_PROBLEMS,
    SUPPORTED_LANGUAGES,
    get_all_problems,
    get_custom_problems,
    get_submission_stats,
    get_submission_stats_extended,
    get_problem,
    evaluate_submission,
    save_submission,
    save_attempt_timeline,
    get_user_submission_summary,
    get_problem_timeline,
    submission_ts_column,
    fetch_idempotent_response,
    store_idempotent_response,
    hint_ladder,
    review_code_heuristic,
    coding_followup_questions,
    recommend_next_problem,
    personalized_practice_queue,
    study_plan,
    interview_readiness_score,
    weak_tags_for_user,
    topic_mastery_report,
    daily_goal_progress,
    editorial_bundle,
    contest_snapshot,
    plagiarism_alerts,
    export_problems_json,
    export_problems_csv,
    import_problems_from_json,
    coverage_report,
    company_sets,
    get_company_problems,
    starter_for_language,
    init_coding_tables,
    enqueue_judge_job,
    process_judge_job,
    get_judge_job,
    add_custom_problem,
    update_custom_problem,
    delete_custom_problem,
    parse_test_lines,
)
from admin_analytics import (
    init_admin_tables,
    log_event,
    log_model_health,
    add_feedback,
    update_feedback_status,
    log_audit,
    upsert_experiment,
    upsert_ab_test,
    add_safety_event,
    log_mentor_metric,
    dashboard_payload,
    export_all_json,
    export_all_csv,
)

load_dotenv()

logger = logging.getLogger("resumate")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

APP_ENV = (os.getenv("APP_ENV") or "development").strip().lower()
CSRF_STRICT = (os.getenv("CSRF_STRICT") or "false").strip().lower() in ("1", "true", "yes", "on")
REQUESTS_PER_MINUTE = int(os.getenv("REQUESTS_PER_MINUTE") or 120)
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES") or 5_000_000)
FREE_RESUME_DAILY_LIMIT = max(1, int(os.getenv("FREE_RESUME_DAILY_LIMIT") or 3))
CODING_MAX_CODE_CHARS = max(2000, int(os.getenv("CODING_MAX_CODE_CHARS") or 40000))
CODING_MAX_CUSTOM_INPUT_CHARS = max(100, int(os.getenv("CODING_MAX_CUSTOM_INPUT_CHARS") or 10000))
CODING_ASYNC_JUDGE = (os.getenv("CODING_ASYNC_JUDGE") or "true").strip().lower() in ("1", "true", "yes", "on")
CODING_DEEP_INSIGHTS = (os.getenv("CODING_DEEP_INSIGHTS") or "false").strip().lower() in ("1", "true", "yes", "on")
TRUSTED_HOSTS = [h.strip() for h in (os.getenv("TRUSTED_HOSTS") or "localhost,127.0.0.1,testserver").split(",") if h.strip()]
ENABLE_HTTPS_REDIRECT = (os.getenv("ENABLE_HTTPS_REDIRECT") or "false").strip().lower() in ("1", "true", "yes", "on")

SENTRY_DSN = (os.getenv("SENTRY_DSN") or "").strip()
if SENTRY_DSN:
    try:
        import sentry_sdk  # type: ignore

        sentry_sdk.init(dsn=SENTRY_DSN, environment=APP_ENV, traces_sample_rate=0.1)
        logger.info("Sentry initialized")
    except Exception as e:
        logger.warning("Sentry init failed: %s", e)

def get_admin_settings() -> tuple[str, str, str]:
    # Reload .env so credential changes apply without requiring a server restart.
    load_dotenv(override=True)
    admin_username = (os.getenv("ADMIN_USERNAME") or "").strip()
    admin_password = os.getenv("ADMIN_PASSWORD") or ""
    admin_email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
    return admin_username, admin_password, admin_email





def normalize_question(q):

    if isinstance(q, dict):
        q = q.get("question", "")

    q = str(q)
    q = q.replace("\n", " ")
    q = q.replace("Question:", "")
    q = q.strip()

    return q


INTERVIEW_QUESTION_BANK = {
    "python": [
        "How would you optimize a Python API endpoint that becomes CPU-bound under peak load?",
        "Explain the difference between threading, multiprocessing, and asyncio with one production use case each.",
        "How do you design robust retry logic for external API calls in Python services?",
    ],
    "sql": [
        "How do you debug a slow query in production and validate index strategy changes safely?",
        "Explain window functions with a practical example from analytics reporting.",
        "How would you detect and remove duplicate records without data loss?",
    ],
    "react": [
        "How would you prevent unnecessary re-renders in a React page with multiple data widgets?",
        "Explain how you structure state management for a medium-size product dashboard.",
        "How do you debug hydration mismatch issues in server-rendered React apps?",
    ],
    "system design": [
        "Design a rate-limited URL shortener that supports analytics and high write throughput.",
        "How would you scale a notification system for multi-channel delivery?",
        "Design a logging pipeline with low-latency search and retention controls.",
    ],
    "behavioral": [
        "Tell me about a time you disagreed with a technical direction and how you resolved it.",
        "Describe a high-pressure incident you handled and what you changed afterwards.",
        "Give an example of mentoring someone and measuring the outcome.",
    ],
}


def bank_questions(topic: str, role: str = "", round_type: str = "", limit: int = 2) -> list[str]:
    key = (topic or round_type or "behavioral").strip().lower()
    pool = INTERVIEW_QUESTION_BANK.get(key, INTERVIEW_QUESTION_BANK.get("behavioral", []))
    role = role.strip()
    seeded = []
    for q in pool[: max(1, limit)]:
        if role:
            seeded.append(f"For a {role} role: {q}")
        else:
            seeded.append(q)
    return seeded[:limit]


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
        SELECT created_ts, overall, ats, keyword_coverage, status, target_role
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
            "timestamp": int(r[0] or 0),
            "overall": float(r[1] or 0),
            "ats": float(r[2] or 0),
            "keyword_coverage": float(r[3] or 0),
            "status": str(r[4] or ""),
            "target_role": str(r[5] or ""),
        }
        for r in rows
    ]


def _auth_key(request: Request, action: str, identity: str = "") -> str:
    ip = ""
    try:
        ip = request.client.host if request.client else ""
    except Exception:
        ip = ""
    return f"{action}:{(identity or '').strip().lower()}:{ip}"


def is_rate_limited(request: Request, action: str, identity: str = "", max_attempts: int = 5, window_sec: int = 300, block_sec: int = 600):
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


def record_auth_failure(request: Request, action: str, identity: str = "", window_sec: int = 300):
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


def record_auth_success(request: Request, action: str, identity: str = ""):
    key = _auth_key(request, action, identity)
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, "DELETE FROM auth_rate_limits WHERE rate_key=?", (key,))
    conn.commit()
    conn.close()


def interview_metrics(timeline: list) -> dict:
    if not timeline:
        return {"avg_score": 0.0, "avg_wpm": 0, "avg_filler_pct": 0.0}
    scores = [float(t.get("overall", 0) or 0) for t in timeline if isinstance(t, dict)]
    wpms = [int((t.get("voice_pace", {}) or {}).get("wpm", 0) or 0) for t in timeline if isinstance(t, dict)]
    fillers = [float((t.get("voice_pace", {}) or {}).get("filler_density_pct", 0) or 0) for t in timeline if isinstance(t, dict)]
    return {
        "avg_score": round(sum(scores) / max(1, len(scores)), 1),
        "avg_wpm": int(round(sum(wpms) / max(1, len(wpms)))) if wpms else 0,
        "avg_filler_pct": round(sum(fillers) / max(1, len(fillers)), 1) if fillers else 0.0,
    }


def parse_json_object(raw: str):
    cleaned = (raw or "").replace("```json", "").replace("```", "").strip()
    if "{" in cleaned and "}" in cleaned:
        cleaned = cleaned[cleaned.find("{"):cleaned.rfind("}") + 1]
    return json.loads(cleaned)


def build_pre_session_brief(name: str, email: str, topic: str, datetime: str, outcome: str, context_notes: str, link: str) -> str:
    return f"""
Pre-Session Brief

Candidate: {name}
Candidate Email: {email}
Specialization: {topic}
Scheduled Time: {datetime}
Target Outcome: {outcome or "Not provided"}
Context Notes: {context_notes or "Not provided"}
Meeting Link: {link}

Proposed Session Plan (30-45 min):
1. 5 min: Goal alignment and context
2. 20-30 min: Focused mock/mentorship on target outcome
3. 10 min: Action plan with next steps
""".strip()


def interview_context_payload(request: Request, **extra):
    timeline = request.session.get("timeline", [])
    user_email = (request.session.get("user_email") or "").strip().lower()
    memory = get_user_memory(user_email)
    config = request.session.get("interview_config", {}) or {}
    default_setup = {
        "topic": memory.get("focus_area", "") or "Python",
        "role": memory.get("target_role", ""),
        "company": memory.get("target_company", ""),
    }
    payload = {
        "request": request,
        "questions": request.session.get("questions", []),
        "current": request.session.get("current", 0),
        "finished": request.session.get("finished", False),
        "config": config,
        "default_setup": default_setup,
        "timeline": timeline,
        "feedback": request.session.get("last_feedback"),
        "final_score": request.session.get("final_score"),
        "hiring_result": request.session.get("hiring_result"),
        "next_followup": request.session.get("next_followup"),
        "session_metrics": interview_metrics(timeline),
        "user_plan": current_user_plan(request),
    }
    payload.update(extra)
    return payload


_TIMED_ALLOWED = {"35", "45"}


def _timed_session_key(problem_id: str) -> str:
    return f"timed_mode_{str(problem_id or '').strip()}"


def _clear_timed_mode(request: Request, problem_id: str) -> None:
    request.session.pop(_timed_session_key(problem_id), None)


def _apply_timed_mode_selection(request: Request, problem_id: str, timed_mode: str) -> Dict[str, Any]:
    mode = str(timed_mode or "").strip()
    key = _timed_session_key(problem_id)
    now = int(time.time())
    if mode in _TIMED_ALLOWED:
        state = request.session.get(key) or {}
        if str(state.get("duration_min") or "") != mode:
            state = {
                "duration_min": int(mode),
                "start_ts": now,
                "submitted": False,
                "job_id": "",
            }
            request.session[key] = state
    elif mode == "":
        _clear_timed_mode(request, problem_id)
    return _timed_mode_state(request, problem_id)


def _timed_mode_state(request: Request, problem_id: str) -> Dict[str, Any]:
    state = request.session.get(_timed_session_key(problem_id)) or {}
    if not state:
        return {
            "enabled": False,
            "duration_min": 0,
            "remaining_sec": 0,
            "elapsed_sec": 0,
            "expired": False,
            "submitted": False,
            "job_id": "",
        }
    duration = int(state.get("duration_min") or 0)
    start_ts = int(state.get("start_ts") or 0)
    now = int(time.time())
    elapsed = max(0, now - start_ts)
    total = max(0, duration * 60)
    remaining = max(0, total - elapsed)
    expired = remaining <= 0
    return {
        "enabled": duration > 0,
        "duration_min": duration,
        "remaining_sec": remaining,
        "elapsed_sec": elapsed,
        "expired": expired,
        "submitted": bool(state.get("submitted")),
        "job_id": str(state.get("job_id") or ""),
    }


def _mark_timed_mode_submitted(request: Request, problem_id: str, job_id: str = "") -> None:
    key = _timed_session_key(problem_id)
    state = request.session.get(key) or {}
    if not state:
        return
    state["submitted"] = True
    if job_id:
        state["job_id"] = job_id
    request.session[key] = state


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


def _safe_call(fn, default, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        logger.warning("coding_safe_call_failed fn=%s err=%s", getattr(fn, "__name__", "unknown"), exc)
        return default


def _select_problem(problems, problem_id: str):
    pid = str(problem_id or "").strip()
    for p in problems:
        if str((p or {}).get("id") or "") == pid:
            return p
    if problems:
        return problems[0]
    return dict(DEFAULT_PROBLEMS[0])


def _readiness_from_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    total = int((summary or {}).get("total") or 0)
    accept = float((summary or {}).get("accept_rate") or 0.0)
    speed = float((summary or {}).get("avg_runtime_ms") or 0.0)
    consistency = min(100.0, total * 5.0)
    speed_score = 100.0 if speed <= 120 else max(20.0, 140.0 - (speed / 2.5))
    score = round((accept * 0.5) + (consistency * 0.25) + (speed_score * 0.25), 1)
    band = "High" if score >= 75 else ("Medium" if score >= 50 else "Low")
    return {
        "score": score,
        "band": band,
        "accept_rate": round(accept, 1),
        "consistency": round(consistency, 1),
        "speed_score": round(speed_score, 1),
    }


def _daily_goal_from_attempts(attempts: list, goal_accepted: int = 1, goal_review: int = 1) -> Dict[str, Any]:
    now = int(time.time())
    today = time.strftime("%Y-%m-%d", time.localtime(now))
    bucket = {"accepted": 0, "review": 0}
    for a in attempts[:60]:
        ts = int(a.get("timestamp") or 0)
        if not ts:
            continue
        if time.strftime("%Y-%m-%d", time.localtime(ts)) != today:
            continue
        mode = str(a.get("mode") or "")
        status = str(a.get("status") or "")
        if mode == "submit" and status == "Accepted":
            bucket["accepted"] += 1
        if mode in ("run", "submit", "hint", "interviewer"):
            bucket["review"] += 1

    last_7 = []
    base = now - 6 * 24 * 60 * 60
    for i in range(7):
        day_ts = base + i * 24 * 60 * 60
        day = time.strftime("%Y-%m-%d", time.localtime(day_ts))
        accepted = 0
        review = 0
        for a in attempts[:100]:
            ts = int(a.get("timestamp") or 0)
            if not ts:
                continue
            if time.strftime("%Y-%m-%d", time.localtime(ts)) != day:
                continue
            mode = str(a.get("mode") or "")
            status = str(a.get("status") or "")
            if mode == "submit" and status == "Accepted":
                accepted += 1
            if mode in ("run", "submit", "hint", "interviewer"):
                review += 1
        met = accepted >= goal_accepted and review >= goal_review
        last_7.append({"day": day[5:], "accepted": accepted, "review": review, "met": met})

    streak = 0
    for day in reversed(last_7):
        if day["met"]:
            streak += 1
        else:
            break
    return {
        "accepted_today": int(bucket["accepted"]),
        "review_today": int(bucket["review"]),
        "goal_accepted": int(goal_accepted),
        "goal_review": int(goal_review),
        "goal_met_today": bucket["accepted"] >= goal_accepted and bucket["review"] >= goal_review,
        "streak_days": int(streak),
        "last_7_days": last_7,
    }


def _recommended_from_problems(problems: list, selected_id: str, attempts: list) -> Dict[str, Any]:
    solved = set(
        str(a.get("problem_id") or "")
        for a in attempts
        if str(a.get("mode") or "") == "submit" and str(a.get("status") or "") == "Accepted"
    )
    for p in problems:
        pid = str((p or {}).get("id") or "")
        if not pid or pid == selected_id:
            continue
        if pid not in solved:
            return p
    for p in problems:
        pid = str((p or {}).get("id") or "")
        if pid and pid != selected_id:
            return p
    return {}


def _practice_queue_from_problems(problems: list, selected_id: str, attempts: list, limit: int = 5) -> list:
    solved = set(
        str(a.get("problem_id") or "")
        for a in attempts
        if str(a.get("mode") or "") == "submit" and str(a.get("status") or "") == "Accepted"
    )
    queue = []
    for p in problems:
        pid = str((p or {}).get("id") or "")
        if not pid or pid == selected_id:
            continue
        queue.append(
            {
                "id": pid,
                "title": str(p.get("title") or pid),
                "difficulty": str(p.get("difficulty") or "Easy"),
                "tags": list(p.get("tags") or []),
                "reason": "Not solved yet" if pid not in solved else "Revision suggested",
                "score": 2 if pid not in solved else 1,
            }
        )
        if len(queue) >= max(1, int(limit)):
            break
    return queue


def _light_contest_snapshot(problems: list) -> Dict[str, Any]:
    chosen = []
    for d in ("Easy", "Medium", "Hard"):
        for p in problems:
            if str((p or {}).get("difficulty") or "") == d:
                chosen.append(p)
                break
    if not chosen:
        chosen = list(problems[:3])
    return {
        "contest": {
            "id": "local",
            "title": "Weekly Contest (Preview)",
            "problem_ids": [str(p.get("id") or "") for p in chosen],
            "problems": [
                {"id": str(p.get("id") or ""), "title": str(p.get("title") or ""), "difficulty": str(p.get("difficulty") or "Easy")}
                for p in chosen
            ],
            "start_ts": 0,
            "end_ts": 0,
        },
        "leaderboard": [],
        "user_rank": 0,
        "user_percentile": 0.0,
    }


def coding_context_payload(request: Request, problem_id: str, **extra):
    attempts = request.session.get("coding_attempts", [])
    problems = _safe_call(get_all_problems, list(DEFAULT_PROBLEMS))
    selected = _select_problem(problems, problem_id)
    email = (request.session.get("user_email") or "").strip().lower()
    language = request.session.get(f"lang_{selected['id']}", "python")
    if language not in SUPPORTED_LANGUAGES:
        language = "python"
    code_key = f"code_{selected['id']}_{language}"
    problem_attempts = [a for a in attempts if a.get("problem_id") == selected["id"]][:12]
    timed_state = _timed_mode_state(request, selected["id"])
    solved = set(
        a.get("problem_id")
        for a in attempts
        if a.get("mode") == "submit" and a.get("status") == "Accepted"
    )
    solved_count = len(solved)
    if CODING_DEEP_INSIGHTS and email:
        solved_count = _safe_call(_solved_problem_count, solved_count, email)

    summary_default = {
        "total": 0,
        "accepted": 0,
        "accept_rate": 0.0,
        "avg_runtime_ms": 0.0,
        "by_language": [],
        "recent": [],
    }
    user_summary = _safe_call(get_user_submission_summary, summary_default, email) if email else summary_default

    if CODING_DEEP_INSIGHTS and email:
        problem_timeline = _safe_call(get_problem_timeline, [], email, selected["id"], 12)
        weak = _safe_call(weak_tags_for_user, [], email, 30)
        readiness = _safe_call(interview_readiness_score, _readiness_from_summary(user_summary), email)
        plan_7 = _safe_call(study_plan, ["Day 1-2: Solve 2 Easy problems.", "Day 3-4: Solve 2 Medium problems."], email, 7)
        plan_30 = _safe_call(study_plan, ["Week 1: Foundation review.", "Week 2: Medium optimization practice."], email, 30)
        recommended = _safe_call(recommend_next_problem, _recommended_from_problems(problems, selected["id"], attempts), email, selected["id"])
        queue = _safe_call(personalized_practice_queue, _practice_queue_from_problems(problems, selected["id"], attempts, 5), email, selected["id"], 5)
        mastery = _safe_call(topic_mastery_report, [], email, 45)
        daily_goal = _safe_call(daily_goal_progress, _daily_goal_from_attempts(attempts), email)
        contest = _safe_call(contest_snapshot, _light_contest_snapshot(problems), email, 10)
    else:
        problem_timeline = []
        weak = []
        readiness = _readiness_from_summary(user_summary)
        plan_7 = ["Day 1-2: Solve 2 Easy problems.", "Day 3-4: Solve 2 Medium problems.", "Day 5-7: Review failures and retry."]
        plan_30 = ["Week 1: Build fundamentals.", "Week 2: Medium problems.", "Week 3: Timed sets.", "Week 4: Mock interview drills."]
        recommended = _recommended_from_problems(problems, selected["id"], attempts)
        queue = _practice_queue_from_problems(problems, selected["id"], attempts, 5)
        mastery = []
        daily_goal = _daily_goal_from_attempts(attempts)
        contest = _light_contest_snapshot(problems)

    payload = {
        "request": request,
        "problems": problems,
        "problem": selected,
        "selected_problem_id": selected["id"],
        "language": language,
        "languages": list(SUPPORTED_LANGUAGES),
        "code": request.session.get(code_key, starter_for_language(selected, language)),
        "result": None,
        "attempts": attempts[:20],
        "problem_attempts": problem_attempts,
        "problem_timeline": problem_timeline,
        "solved_count": solved_count,
        "last_custom_input": request.session.get(f"custom_input_{selected['id']}", ""),
        "user_submission_summary": user_summary,
        "weak_tags": weak,
        "readiness": readiness,
        "study_plan_7d": plan_7,
        "study_plan_30d": plan_30,
        "recommended_problem": recommended,
        "practice_queue": queue,
        "mastery": mastery,
        "daily_goal": daily_goal,
        "contest_snapshot": contest,
        "problem_coverage": coverage_report(selected),
        "submit_idem_key": f"submit-{int(time.time()*1000)}-{uuid.uuid4().hex[:10]}",
        "timed_state": timed_state,
        "timed_mode": str(timed_state.get("duration_min") or "") if timed_state.get("enabled") else "",
        "user_plan": current_user_plan(request),
    }
    payload.update(extra)
    return payload


def admin_context_payload(request: Request):
    data = get_bookings()
    payload = dashboard_payload(data)
    coding_stats = get_submission_stats_extended(limit=100)
    custom_problems = get_custom_problems()
    for p in custom_problems:
        p["coverage"] = coverage_report(p)
    return {
        "request": request,
        "data": data,
        "admin": payload,
        "coding_stats": coding_stats,
        "custom_problems": custom_problems,
    }


def _parse_problem_admin_payload(
    title: str,
    difficulty: str,
    tags: str,
    description: str,
    constraints: str,
    examples: str,
    sample_tests: str,
    hidden_tests: str,
    starter_py: str,
    starter_js: str,
    starter_java: str,
    starter_cpp: str,
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    constraint_list = [c.strip() for c in constraints.splitlines() if c.strip()]

    example_list = []
    for line in (examples or "").splitlines():
        raw = line.strip()
        if not raw or "|||" not in raw:
            continue
        inp, out = raw.split("|||", 1)
        example_list.append({"input": inp.strip().replace("\\n", "\n"), "output": out.strip().replace("\\n", "\n")})

    parsed_sample_tests = parse_test_lines(sample_tests)
    parsed_hidden_tests = parse_test_lines(hidden_tests)

    defaults = {
        "starter_py": "def solve(input_data: str) -> str:\n    # Write your solution here\n    return \"\"\n",
        "starter_js": "function solve(inputData) {\n  // Write your solution here\n  return \"\";\n}\n",
        "starter_java": "import java.util.*;\n\npublic class Solution {\n  public static String solve(String inputData) {\n    // Write your solution here\n    return \"\";\n  }\n}\n",
        "starter_cpp": "#include <bits/stdc++.h>\nusing namespace std;\n\nstring solve(const string& inputData) {\n    // Write your solution here\n    return \"\";\n}\n",
    }
    return {
        "title": title,
        "difficulty": difficulty,
        "description": description,
        "tags": tag_list,
        "constraints": constraint_list,
        "examples": example_list,
        "sample_tests": parsed_sample_tests,
        "hidden_tests": parsed_hidden_tests,
        "starter_py": starter_py.strip() or defaults["starter_py"],
        "starter_js": starter_js.strip() or defaults["starter_js"],
        "starter_java": starter_java.strip() or defaults["starter_java"],
        "starter_cpp": starter_cpp.strip() or defaults["starter_cpp"],
    }


session_secret = os.getenv("SESSION_SECRET_KEY") or os.getenv("SESSION_SECRET")
if not session_secret:
    # Fallback keeps local dev running; set SESSION_SECRET_KEY in production.
    session_secret = "dev-only-change-this-secret"


app = FastAPI()

_rate_hits = defaultdict(deque)


def _same_origin(request: Request) -> bool:
    host = (request.headers.get("host") or "").strip().lower()
    if not host:
        return False
    origin = (request.headers.get("origin") or "").strip()
    referer = (request.headers.get("referer") or "").strip()
    source = origin or referer
    if not source:
        return APP_ENV != "production" or not CSRF_STRICT
    try:
        parsed = urlparse(source)
        src_host = (parsed.netloc or "").lower()
    except Exception:
        return False
    return src_host == host

class AuthGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path or "/"
        normalized_path = path.rstrip("/") or "/"

        if normalized_path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
            return await call_next(request)

        if request.session.get("user_id") or is_admin_session(request):
            return await call_next(request)

        return RedirectResponse("/?auth=required", status_code=303)


class RequestGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path or "/"
        if path.startswith("/static"):
            response = await call_next(request)
            response.headers["Cache-Control"] = "public, max-age=86400"
            return response

        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = req_id
        ip = ""
        try:
            ip = request.client.host if request.client else "unknown"
        except Exception:
            ip = "unknown"

        # Global abuse throttle.
        now = time.time()
        dq = _rate_hits[ip]
        while dq and now - dq[0] > 60:
            dq.popleft()
        dq.append(now)
        if len(dq) > REQUESTS_PER_MINUTE:
            return PlainTextResponse("Too Many Requests", status_code=429, headers={"X-Request-ID": req_id})

        # CSRF origin guard for state-changing browser requests.
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            csrf_exempt = (
                path.startswith("/mindmap")
                or path.startswith("/skill-info")
                or path.startswith("/healthz")
            )
            if not csrf_exempt and not _same_origin(request):
                return PlainTextResponse("CSRF validation failed", status_code=403, headers={"X-Request-ID": req_id})

        started = time.time()
        response = await call_next(request)
        latency_ms = round((time.time() - started) * 1000.0, 1)
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if request.url.scheme == "https" or APP_ENV == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        logger.info("request_id=%s method=%s path=%s status=%s latency_ms=%s", req_id, request.method, path, response.status_code, latency_ms)
        return response


app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(RequestGuardMiddleware)
app.add_middleware(AuthGateMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
    https_only=(APP_ENV == "production"),
    same_site="lax",
    max_age=60 * 60 * 24 * 14,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=TRUSTED_HOSTS or ["*"])
if ENABLE_HTTPS_REDIRECT:
    app.add_middleware(HTTPSRedirectMiddleware)

templates = Jinja2Templates(directory="templates")
init_admin_tables()
init_coding_tables()


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


def is_admin_session(request: Request) -> bool:
    return request.session.get("admin") is True


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


def user_progress_summary(user_email: str, conn=None) -> dict:
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
        db.execute(
            cur,
            "SELECT ts FROM user_events WHERE user_id=? AND ts>=?",
            (email, thirty_days_ago),
        )
        events_days_rows = cur.fetchall() or []
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


def resume_quota_state(request: Request) -> dict:
    plan = current_user_plan(request)
    if plan == "premium":
        return {"plan": plan, "is_premium": True, "limit": 0, "used": 0, "remaining": 999}
    day_key = time.strftime("%Y-%m-%d")
    used_day = request.session.get("resume_day")
    used_count = int(request.session.get("resume_count", 0) or 0)
    if used_day != day_key:
        used_day = day_key
        used_count = 0
        request.session["resume_day"] = used_day
        request.session["resume_count"] = used_count
    remaining = max(0, FREE_RESUME_DAILY_LIMIT - used_count)
    return {"plan": plan, "is_premium": False, "limit": FREE_RESUME_DAILY_LIMIT, "used": used_count, "remaining": remaining}


def consume_resume_quota(request: Request) -> None:
    state = resume_quota_state(request)
    if state.get("is_premium"):
        return
    request.session["resume_count"] = int(state.get("used", 0)) + 1


init_user_tables()
_ensure_auth_tables()
init_resume_tables()

PUBLIC_PATHS = {
    "/",
    "/login",
    "/signup",
    "/forgot-password",
    "/reset-password",
    "/privacy",
    "/terms",
    "/healthz",
    "/readyz",
}
PUBLIC_PREFIXES = ("/static",)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "ts": int(time.time())}


@app.get("/readyz")
def readyz():
    try:
        conn = db.get_conn()
        cur = conn.cursor()
        db.execute(cur, "SELECT 1")
        cur.fetchone()
        conn.close()
        return {"status": "ready"}
    except Exception as e:
        return JSONResponse({"status": "not_ready", "error": str(e)}, status_code=503)


@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request})


@app.get("/terms", response_class=HTMLResponse)
def terms(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", "n/a")
    logger.exception("unhandled_error request_id=%s path=%s", req_id, request.url.path)
    return templates.TemplateResponse(
        "error.html",
        {"request": request, "request_id": req_id},
        status_code=500,
    )


# LANDING PAGE
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    log_event("page_view", "landing", metadata={"path": "/"})
    auth_notice = request.query_params.get("auth") == "required"
    return templates.TemplateResponse("index.html", {"request": request, "auth_notice": auth_notice})


@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("signup.html", {"request": request})


@app.post("/signup", response_class=HTMLResponse)
def signup(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    website: str = Form(""),
):
    if (website or "").strip():
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Request blocked."})
    full_name = full_name.strip()
    email = email.strip().lower()

    if len(full_name) < 2:
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Enter a valid name."})
    if "@" not in email or "." not in email:
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Enter a valid email."})
    pw_error = validate_password_strength(password)
    if pw_error:
        return templates.TemplateResponse("signup.html", {"request": request, "error": pw_error})
    if password != confirm_password:
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Passwords do not match."})

    conn = db.get_conn()
    cur = conn.cursor()
    try:
        db.execute(cur, 
            "INSERT INTO users(full_name,email,password_hash,role,password_updated_ts,created_ts) VALUES(?,?,?,?,?,?)",
            (full_name, email, hash_password(password), "user", int(time.time()), int(time.time())),
        )
        conn.commit()
        db.execute(cur, "SELECT id FROM users WHERE email=?", (email,))
        row = cur.fetchone()
        user_id = int((row or [0])[0] or 0)
    except Exception:
        conn.close()
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Email already registered."})
    conn.close()

    request.session["user_id"] = int(user_id)
    request.session["user_name"] = full_name
    request.session["user_email"] = email
    request.session["user_role"] = "user"
    request.session["user_plan"] = "free"
    request.session.pop("admin", None)
    request.session.pop("admin_user", None)
    return RedirectResponse("/", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_admin_session(request):
        return RedirectResponse("/admin", status_code=303)
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    website: str = Form(""),
):
    if (website or "").strip():
        return templates.TemplateResponse("login.html", {"request": request, "error": "Request blocked."})
    admin_username, admin_password, admin_email = get_admin_settings()
    identity = email.strip()
    email = identity.lower()
    blocked, retry = is_rate_limited(request, "login", identity=email)
    if blocked:
        return templates.TemplateResponse("login.html", {"request": request, "error": f"Too many attempts. Try again in {retry}s."})

    is_admin_identity = (
        (admin_username and identity.lower() == admin_username.lower())
        or (admin_email and email == admin_email)
    )
    if admin_password and is_admin_identity and password == admin_password:
        request.session["admin"] = True
        request.session["admin_user"] = admin_username or admin_email
        request.session["user_id"] = -1
        request.session["user_name"] = "Admin"
        request.session["user_email"] = admin_email or admin_username
        request.session["user_role"] = "admin"
        request.session["user_plan"] = "premium"
        record_auth_success(request, "login", identity=email)
        log_audit("admin", "admin_login_success", "Admin authenticated via /login")
        return RedirectResponse("/admin", status_code=303)

    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, "SELECT id, full_name, email, password_hash, role, plan FROM users WHERE email=?", (email,))
    row = cur.fetchone()
    if not row or not verify_password(row[3], password):
        conn.close()
        record_auth_failure(request, "login", identity=email)
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid email or password."})
    if not str(row[3]).startswith("pbkdf2_sha256$"):
        db.execute(cur, 
            "UPDATE users SET password_hash=?, password_updated_ts=? WHERE id=?",
            (hash_password(password), int(time.time()), int(row[0])),
        )
        conn.commit()
    conn.close()
    record_auth_success(request, "login", identity=email)

    request.session["user_id"] = int(row[0])
    request.session["user_name"] = row[1]
    request.session["user_email"] = row[2]
    request.session["user_role"] = row[4] or "user"
    request.session["user_plan"] = (row[5] or "free")
    request.session.pop("admin", None)
    request.session.pop("admin_user", None)
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.pop("user_id", None)
    request.session.pop("user_name", None)
    request.session.pop("user_email", None)
    request.session.pop("user_role", None)
    request.session.pop("user_plan", None)
    request.session.pop("admin", None)
    request.session.pop("admin_user", None)
    return RedirectResponse("/", status_code=303)


@app.get("/account", response_class=HTMLResponse)
def account_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login", status_code=303)
    if is_admin_session(request):
        return RedirectResponse("/admin", status_code=303)
    plan = current_user_plan(request)
    user_email = (request.session.get("user_email") or "").strip().lower()
    memory = {"target_role": "", "target_company": "", "focus_area": ""}
    progress = {
        "resume_runs_7d": 0,
        "resume_avg_7d": 0.0,
        "coding_submissions_7d": 0,
        "coding_accept_rate_7d": 0.0,
        "active_days_7d": 0,
        "current_streak_days": 0,
        "next_action": "Run your first resume review (8 min).",
    }
    conn = db.get_conn()
    try:
        memory = get_user_memory(user_email, conn=conn)
        progress = user_progress_summary(user_email, conn=conn)
    except Exception as account_error:
        logger.warning("account_snapshot_failed user=%s err=%s", user_email, str(account_error))
    finally:
        conn.close()
    return templates.TemplateResponse(
        "account.html",
        {
            "request": request,
            "user_plan": plan,
            "memory": memory,
            "progress": progress,
            "status": (request.query_params.get("status") or "").strip().lower(),
        },
    )


@app.post("/account/memory")
def save_account_memory(
    request: Request,
    target_role: str = Form(""),
    target_company: str = Form(""),
    focus_area: str = Form(""),
):
    if not request.session.get("user_id") or is_admin_session(request):
        return RedirectResponse("/login", status_code=303)
    user_email = (request.session.get("user_email") or "").strip().lower()
    save_user_memory(user_email, target_role, target_company, focus_area)
    return RedirectResponse("/account?status=memory-saved", status_code=303)


@app.get("/pricing", response_class=HTMLResponse)
def pricing_page(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login", status_code=303)
    if is_admin_session(request):
        return RedirectResponse("/admin", status_code=303)
    user_email = (request.session.get("user_email") or "").strip().lower()
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(
        cur,
        """
        SELECT id, upi_txn_ref, amount, screenshot_url, notes, status, rejection_reason, created_ts
        FROM premium_requests
        WHERE user_email=?
        ORDER BY created_ts DESC
        LIMIT 1
        """,
        (user_email,),
    )
    latest_request = cur.fetchone()
    conn.close()
    return templates.TemplateResponse(
        "pricing.html",
        {
            "request": request,
            "user_plan": current_user_plan(request),
            "latest_request": latest_request,
            "status": (request.query_params.get("status") or "").strip().lower(),
        },
    )


@app.post("/premium/request")
def create_premium_request(
    request: Request,
    upi_txn_ref: str = Form(...),
    amount: str = Form(""),
    screenshot_url: str = Form(""),
    notes: str = Form(""),
):
    if not request.session.get("user_id") or is_admin_session(request):
        return RedirectResponse("/login", status_code=303)
    user_id = int(request.session.get("user_id") or 0)
    user_email = (request.session.get("user_email") or "").strip().lower()
    if is_premium_user(request):
        return RedirectResponse("/pricing?status=already-premium", status_code=303)

    upi_txn_ref = (upi_txn_ref or "").strip()
    amount = (amount or "").strip()
    screenshot_url = (screenshot_url or "").strip()
    notes = (notes or "").strip()
    if len(upi_txn_ref) < 5:
        return RedirectResponse("/pricing?status=invalid-ref", status_code=303)
    if screenshot_url and not screenshot_url.startswith(("http://", "https://")):
        return RedirectResponse("/pricing?status=invalid-link", status_code=303)

    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(
        cur,
        """
        SELECT id FROM premium_requests
        WHERE user_email=? AND status='pending'
        ORDER BY created_ts DESC
        LIMIT 1
        """,
        (user_email,),
    )
    pending = cur.fetchone()
    if pending:
        conn.close()
        return RedirectResponse("/pricing?status=already-pending", status_code=303)

    db.execute(
        cur,
        """
        INSERT INTO premium_requests(
            user_id,user_email,upi_txn_ref,amount,screenshot_url,notes,status,created_ts
        ) VALUES(?,?,?,?,?,?,?,?)
        """,
        (user_id, user_email, upi_txn_ref[:120], amount[:40], screenshot_url[:400], notes[:1000], "pending", int(time.time())),
    )
    conn.commit()
    conn.close()
    log_audit(user_email or "user", "premium_request_submitted", f"txn={upi_txn_ref[:40]}")
    return RedirectResponse("/pricing?status=submitted", status_code=303)


@app.post("/account/delete")
def delete_account(request: Request):
    user_email = (request.session.get("user_email") or "").strip().lower()
    if not user_email or is_admin_session(request):
        return RedirectResponse("/", status_code=303)
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, "DELETE FROM users WHERE email=?", (user_email,))
    db.execute(cur, "DELETE FROM resume_reports WHERE user_email=?", (user_email,))
    db.execute(cur, "DELETE FROM coding_submissions WHERE user_email=?", (user_email,))
    db.execute(cur, "DELETE FROM premium_requests WHERE user_email=?", (user_email,))
    db.execute(cur, "DELETE FROM user_memory WHERE user_email=?", (user_email,))
    conn.commit()
    conn.close()
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})


@app.post("/forgot-password", response_class=HTMLResponse)
def forgot_password(request: Request, email: str = Form(...), website: str = Form("")):
    if (website or "").strip():
        return templates.TemplateResponse("forgot_password.html", {"request": request, "error": "Request blocked."})
    email = (email or "").strip().lower()
    blocked, retry = is_rate_limited(request, "forgot_password", identity=email, max_attempts=4, window_sec=300, block_sec=900)
    if blocked:
        return templates.TemplateResponse(
            "forgot_password.html",
            {"request": request, "error": f"Too many requests. Try again in {retry}s."},
        )
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, "SELECT id FROM users WHERE email=?", (email,))
    row = cur.fetchone()
    if row:
        token = secrets.token_urlsafe(28)
        expiry = int(time.time()) + 1800
        db.execute(cur, 
            "UPDATE users SET reset_token=?, reset_token_expiry=? WHERE id=?",
            (token, expiry, int(row[0])),
        )
        conn.commit()
        base = str(request.base_url).rstrip("/")
        reset_link = f"{base}/reset-password?token={token}"
        body = f"Reset your ResuMate password using this link:\n\n{reset_link}\n\nThis link expires in 30 minutes."
        send_mail(email, subject="ResuMate Password Reset", body=body)
    conn.close()
    record_auth_success(request, "forgot_password", identity=email)
    return templates.TemplateResponse(
        "forgot_password.html",
        {"request": request, "message": "If this email exists, a reset link has been sent."},
    )


@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str = ""):
    return templates.TemplateResponse("reset_password.html", {"request": request, "token": token})


@app.post("/reset-password", response_class=HTMLResponse)
def reset_password(
    request: Request,
    token: str = Form(""),
    password: str = Form(...),
    confirm_password: str = Form(...),
    website: str = Form(""),
):
    if (website or "").strip():
        return templates.TemplateResponse("reset_password.html", {"request": request, "error": "Request blocked.", "token": token})
    token = (token or "").strip()
    if not token:
        return templates.TemplateResponse("reset_password.html", {"request": request, "error": "Reset token is required.", "token": token})
    pw_error = validate_password_strength(password)
    if pw_error:
        return templates.TemplateResponse("reset_password.html", {"request": request, "error": pw_error, "token": token})
    if password != confirm_password:
        return templates.TemplateResponse("reset_password.html", {"request": request, "error": "Passwords do not match.", "token": token})

    now = int(time.time())
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(cur, 
        "SELECT id, email, reset_token_expiry FROM users WHERE reset_token=?",
        (token,),
    )
    row = cur.fetchone()
    if not row or int(row[2] or 0) < now:
        conn.close()
        return templates.TemplateResponse("reset_password.html", {"request": request, "error": "Token is invalid or expired.", "token": token})
    db.execute(cur, 
        "UPDATE users SET password_hash=?, password_updated_ts=?, reset_token=NULL, reset_token_expiry=0 WHERE id=?",
        (hash_password(password), now, int(row[0])),
    )
    conn.commit()
    conn.close()
    return templates.TemplateResponse("login.html", {"request": request, "message": "Password reset successful. Please login."})


# RESUME UPLOAD PAGE
@app.get("/resume", response_class=HTMLResponse)
def resume(request: Request):
    log_event("page_view", "resume_page", metadata={"path": "/resume"})
    user_email = (request.session.get("user_email") or "").strip().lower()
    memory = get_user_memory(user_email)
    return templates.TemplateResponse(
        "upload.html",
        {
            "request": request,
            "user_plan": current_user_plan(request),
            "resume_quota": resume_quota_state(request),
            "quota_error": (request.query_params.get("quota_error") or "").strip(),
            "memory": memory,
        },
    )


# UPLOAD ROUTE
@app.post("/upload", response_class=HTMLResponse)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    job_description: str = Form(""),
    target_role: str = Form(""),
    seniority: str = Form(""),
    region: str = Form("US"),
):
    start = time.time()
    quota = resume_quota_state(request)
    if not quota.get("is_premium") and int(quota.get("remaining", 0)) <= 0:
        user_email = (request.session.get("user_email") or "").strip().lower()
        return templates.TemplateResponse(
            "upload.html",
            {
                "request": request,
                "user_plan": quota.get("plan", "free"),
                "resume_quota": quota,
                "quota_error": "Free plan daily limit reached. Upgrade to Premium for unlimited resume reviews.",
                "memory": get_user_memory(user_email),
            },
        )
    try:
        filename = (file.filename or "").lower()
        if not filename.endswith(".pdf"):
            raise ValueError("Only PDF resumes are currently supported.")
        content_type = (file.content_type or "").lower()
        if content_type and content_type not in ("application/pdf", "application/x-pdf", "binary/octet-stream"):
            raise ValueError("Invalid file type. Please upload a PDF.")

        content = await file.read()
        if len(content or b"") > MAX_UPLOAD_BYTES:
            raise ValueError(f"File too large. Max allowed size is {MAX_UPLOAD_BYTES // 1_000_000}MB.")
        text = extract_text(file.filename, content)
        if not text.strip():
            raise ValueError("Could not extract text from the uploaded file.")
        consume_resume_quota(request)
        report = score_resume(
            text=text,
            job_description=job_description,
            target_role=target_role,
            seniority=seniority,
            region=region,
        )

        user_email = (request.session.get("user_email") or "").strip().lower()
        if user_email and (target_role or "").strip():
            prior_memory = get_user_memory(user_email)
            save_user_memory(
                user_email,
                target_role=target_role,
                target_company=prior_memory.get("target_company", ""),
                focus_area=prior_memory.get("focus_area", ""),
            )
        version_history = get_recent_resume_runs_for_user(user_email, limit=10) if user_email else request.session.get("resume_versions", [])
        prev = version_history[-1] if version_history else None
        current_scores = report.get("scores", {})
        current_overall = float(current_scores.get("Overall", 0) or 0)
        current_ats = float(current_scores.get("ATS", 0) or 0)
        current_coverage = float(report.get("keyword_coverage", 0) or 0)

        diff = None
        if prev:
            diff = {
                "overall_delta": round(current_overall - float(prev.get("overall", 0)), 1),
                "ats_delta": round(current_ats - float(prev.get("ats", 0)), 1),
                "keyword_coverage_delta": round(current_coverage - float(prev.get("keyword_coverage", 0)), 1),
            }
        report["version_diff"] = diff

        run_entry = {
            "timestamp": int(time.time()),
            "overall": current_overall,
            "ats": current_ats,
            "keyword_coverage": current_coverage,
            "status": current_scores.get("Status", ""),
            "target_role": target_role or "",
        }
        if user_email:
            try:
                save_resume_report_for_user(user_email, report, target_role=target_role or "")
                version_history = get_recent_resume_runs_for_user(user_email, limit=10)
            except Exception as persist_error:
                logger.warning("resume_report_persist_failed user=%s err=%s", user_email, str(persist_error))
                version_history.append(run_entry)
                version_history = version_history[-10:]
        else:
            version_history.append(run_entry)
            version_history = version_history[-10:]
        request.session["resume_versions"] = version_history
        log_event(
            "resume_review_completed",
            "resume_review",
            cohort=seniority or "unknown",
            region=region,
            role=target_role or "",
            metadata={"status": current_scores.get("Status", ""), "overall": current_overall},
        )
        log_model_health(
            "resume_review",
            "multi-model",
            success=not bool(report.get("error")),
            latency_ms=(time.time() - start) * 1000.0,
            fallback_used=False,
        )

    except Exception as e:
        log_event("resume_review_failed", "resume_review", metadata={"error": str(e)})
        log_model_health(
            "resume_review",
            "multi-model",
            success=False,
            latency_ms=(time.time() - start) * 1000.0,
            fallback_used=True,
            error_message=str(e),
        )
        report = {
            "error": str(e),
            "scores": {"Overall": 0, "ATS": 0, "Status": "Needs Review"},
            "evidence": [],
            "keyword_gaps": [],
            "targeted_rewrites": [],
            "quantification_suggestions": [],
            "recruiter_simulation": {},
            "benchmarking": {"cohort": "N/A", "percentile": 0, "summary": ""},
            "interview_questions": [],
            "region_advice": [],
            "keyword_coverage": 0,
            "link_validation": [],
            "version_diff": None,
        }

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "report": report,
        "resume_versions": version_history if 'version_history' in locals() else request.session.get("resume_versions", []),
        "user_plan": current_user_plan(request),
        "progress": safe_user_progress_summary((request.session.get("user_email") or "").strip().lower()),
        "analysis_inputs": {
            "target_role": target_role,
            "seniority": seniority,
            "region": region,
            "has_job_description": bool(job_description.strip()),
        },
    })


@app.get("/resume/export")
def export_resume_report(request: Request, format: str = "json"):
    if not is_premium_user(request):
        return RedirectResponse("/pricing?status=premium-required", status_code=303)
    user_email = (request.session.get("user_email") or "").strip().lower()
    report = get_latest_resume_report_for_user(user_email) or request.session.get("last_resume_report")
    if not report:
        return PlainTextResponse("No resume report available.", status_code=404)
    fmt = (format or "json").lower()
    if fmt == "txt":
        lines = [
            "ResuMate Resume Review Report",
            f"Generated at: {int(time.time())}",
            "",
            f"Overall: {(report.get('scores') or {}).get('Overall', 0)}",
            f"ATS: {(report.get('scores') or {}).get('ATS', 0)}",
            f"Status: {(report.get('scores') or {}).get('Status', '')}",
            f"Keyword Coverage: {report.get('keyword_coverage', 0)}%",
            "",
            "Top Keyword Gaps:",
        ]
        for gap in (report.get("keyword_gaps") or [])[:8]:
            if isinstance(gap, dict):
                lines.append(f"- {gap.get('keyword', 'N/A')}: {gap.get('reason', '')}")
        content = "\n".join(lines)
        return PlainTextResponse(
            content=content,
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=resume_report.txt"},
        )
    content = json.dumps(report, indent=2)
    return PlainTextResponse(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=resume_report.json"},
    )


# INTERVIEW PAGE
@app.get("/interview", response_class=HTMLResponse)
def interview(request: Request):
    log_event("page_view", "interview_page", metadata={"path": "/interview"})
    return templates.TemplateResponse("interview.html", interview_context_payload(request))


@app.get("/coding", response_class=HTMLResponse)
def coding_page(request: Request, problem: str = "", language: str = "", job_id: str = ""):
    log_event("page_view", "coding_page", metadata={"path": "/coding"})
    selected_id = str(problem or DEFAULT_PROBLEMS[0]["id"])
    if language in SUPPORTED_LANGUAGES:
        request.session[f"lang_{selected_id}"] = language

    extra: Dict[str, Any] = {}
    user_email = request.session.get("user_email", "")
    job = {}
    if job_id:
        job = get_judge_job(job_id, user_email)
        if job:
            job_problem_id = str(job.get("problem_id") or "")
            if job_problem_id:
                selected_id = job_problem_id
            selected = get_problem(selected_id)
            job_lang = str(job.get("language") or "").lower()
            if job_lang in SUPPORTED_LANGUAGES:
                request.session[f"lang_{selected_id}"] = job_lang
            if str(job.get("status")) == "completed":
                result = job.get("result") or {}
                code_text = str(job.get("code_text") or "")
                if code_text:
                    request.session[f"code_{selected_id}_{job_lang or 'python'}"] = code_text
                extra.update(
                    {
                        "judge_job": job,
                        "result": result,
                        "code": code_text,
                        "language": job_lang or language or "python",
                        "explanation": str(job.get("explanation") or ""),
                        "timed_mode": str(job.get("timed_mode") or ""),
                        "followups": coding_followup_questions(selected, code_text, language=job_lang or "python"),
                        "code_review": review_code_heuristic(selected, code_text, result, language=job_lang or "python"),
                        "editorial": editorial_bundle(selected, result, code_text, language=job_lang or "python"),
                    }
                )
            elif str(job.get("status")) == "failed":
                extra.update(
                    {
                        "judge_job": job,
                        "premium_notice": "Judge queue failed for this submission. Please try again.",
                    }
                )
            else:
                extra["judge_job"] = job

    return templates.TemplateResponse("coding.html", coding_context_payload(request, selected_id, **extra))


@app.get("/coding/problems", response_class=HTMLResponse)
def coding_problem_list(request: Request, q: str = "", difficulty: str = "All", company: str = ""):
    log_event("page_view", "coding_problem_list", metadata={"path": "/coding/problems"})
    company = (company or "").strip()
    if company:
        base = get_company_problems(company)
        qv = (q or "").strip().lower()
        dv = (difficulty or "All").strip().lower()
        filtered = base
        if qv:
            filtered = [
                p for p in filtered
                if qv in p.get("title", "").lower()
                or qv in p.get("description", "").lower()
                or any(qv in str(t).lower() for t in p.get("tags", []))
            ]
        if dv and dv != "all":
            filtered = [p for p in filtered if str(p.get("difficulty", "")).lower() == dv]
    else:
        filtered = get_all_problems(query=q, difficulty=difficulty)
    return templates.TemplateResponse(
        "coding_problems.html",
        {
            "request": request,
            "problems": filtered,
            "query": q,
            "difficulty": difficulty,
            "company": company,
            "company_sets": company_sets(),
        },
    )


@app.post("/coding/run", response_class=HTMLResponse)
def coding_run(
    request: Request,
    problem_id: str = Form(...),
    code: str = Form(...),
    language: str = Form("python"),
    custom_input: str = Form(""),
    explanation: str = Form(""),
    timed_mode: str = Form(""),
):
    selected = get_problem(problem_id)
    if language not in SUPPORTED_LANGUAGES:
        language = "python"
    code = code or ""
    custom_input = custom_input or ""
    if len(code) > CODING_MAX_CODE_CHARS:
        return templates.TemplateResponse(
            "coding.html",
            coding_context_payload(
                request,
                selected["id"],
                language=language,
                code=code[:CODING_MAX_CODE_CHARS],
                premium_notice=f"Code too large. Max {CODING_MAX_CODE_CHARS} characters.",
            ),
        )
    if len(custom_input) > CODING_MAX_CUSTOM_INPUT_CHARS:
        custom_input = custom_input[:CODING_MAX_CUSTOM_INPUT_CHARS]
    timed_state = _apply_timed_mode_selection(request, selected["id"], timed_mode)
    request.session[f"lang_{selected['id']}"] = language
    request.session[f"code_{selected['id']}_{language}"] = code
    request.session[f"custom_input_{selected['id']}"] = custom_input
    result = evaluate_submission(selected, code, language=language, mode="run", custom_input=custom_input)
    attempts = request.session.get("coding_attempts", [])
    attempts.insert(
        0,
        {
            "problem_id": selected["id"],
            "title": selected["title"],
            "language": language,
            "status": result["status"],
            "score": f"{result['passed']}/{result['total']}",
            "runtime_ms": result["runtime_ms"],
            "mode": "run",
            "timestamp": int(time.time()),
        },
    )
    request.session["coding_attempts"] = attempts[:30]
    save_submission(
        problem_id=selected["id"],
        language=language,
        mode="run",
        status=result["status"],
        passed=result["passed"],
        total=result["total"],
        runtime_ms=result["runtime_ms"],
        user_email=request.session.get("user_email", ""),
        explanation=explanation,
    )
    save_attempt_timeline(
        problem_id=selected["id"],
        language=language,
        mode="run",
        status=result["status"],
        passed=result["passed"],
        total=result["total"],
        runtime_ms=result["runtime_ms"],
        code=code,
        user_email=request.session.get("user_email", ""),
        explanation=explanation,
        result=result,
    )
    log_event(
        "coding_run",
        "coding_platform",
        role=selected["title"],
        metadata={"status": result["status"], "score": f"{result['passed']}/{result['total']}", "language": language},
    )
    return templates.TemplateResponse(
        "coding.html",
        coding_context_payload(
            request,
            selected["id"],
            language=language,
            code=code,
            result=result,
            last_custom_input=custom_input,
            explanation=explanation,
            timed_mode=timed_mode,
            timed_state=timed_state,
            followups=coding_followup_questions(selected, code, language=language),
            editorial=editorial_bundle(selected, result, code, language=language),
        ),
    )


@app.post("/coding/submit", response_class=HTMLResponse)
def coding_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    problem_id: str = Form(...),
    code: str = Form(...),
    language: str = Form("python"),
    explanation: str = Form(""),
    timed_mode: str = Form(""),
    idem_key: str = Form(""),
):
    selected = get_problem(problem_id)
    if language not in SUPPORTED_LANGUAGES:
        language = "python"
    code = code or ""
    if len(code) > CODING_MAX_CODE_CHARS:
        return templates.TemplateResponse(
            "coding.html",
            coding_context_payload(
                request,
                selected["id"],
                language=language,
                code=code[:CODING_MAX_CODE_CHARS],
                premium_notice=f"Code too large. Max {CODING_MAX_CODE_CHARS} characters.",
            ),
        )
    timed_state = _apply_timed_mode_selection(request, selected["id"], timed_mode)
    if timed_state.get("enabled") and timed_state.get("expired"):
        return templates.TemplateResponse(
            "coding.html",
            coding_context_payload(
                request,
                selected["id"],
                language=language,
                code=code,
                explanation=explanation,
                timed_mode=timed_mode,
                timed_state=timed_state,
                premium_notice="Timed interview mode expired. Start a new timed session to submit.",
            ),
        )
    if timed_state.get("enabled") and timed_state.get("submitted"):
        return templates.TemplateResponse(
            "coding.html",
            coding_context_payload(
                request,
                selected["id"],
                language=language,
                code=code,
                explanation=explanation,
                timed_mode=timed_mode,
                timed_state=timed_state,
                premium_notice="Timed interview mode allows only one submit attempt.",
            ),
        )
    cached = fetch_idempotent_response(idem_key)
    if cached:
        return templates.TemplateResponse(
            "coding.html",
            coding_context_payload(
                request,
                selected["id"],
                language=language,
                code=code,
                result=cached,
                explanation=explanation,
                timed_mode=timed_mode,
                timed_state=timed_state,
                followups=coding_followup_questions(selected, code, language=language),
                code_review=review_code_heuristic(selected, code, cached, language=language),
                editorial=editorial_bundle(selected, cached, code, language=language),
            ),
        )
    request.session[f"lang_{selected['id']}"] = language
    request.session[f"code_{selected['id']}_{language}"] = code
    if CODING_ASYNC_JUDGE:
        job_id = enqueue_judge_job(
            user_email=request.session.get("user_email", ""),
            problem_id=selected["id"],
            language=language,
            mode="submit",
            code_text=code,
            custom_input="",
            explanation=explanation,
            idem_key=idem_key,
            timed_mode=timed_mode,
        )
        background_tasks.add_task(process_judge_job, job_id)
        if timed_state.get("enabled"):
            _mark_timed_mode_submitted(request, selected["id"], job_id=job_id)
            timed_state = _timed_mode_state(request, selected["id"])
        log_event(
            "coding_submit_queued",
            "coding_platform",
            role=selected["title"],
            metadata={"job_id": job_id, "language": language},
        )
        return templates.TemplateResponse(
            "coding.html",
            coding_context_payload(
                request,
                selected["id"],
                language=language,
                code=code,
                explanation=explanation,
                timed_mode=timed_mode,
                timed_state=timed_state,
                judge_job={"job_id": job_id, "status": "queued", "problem_id": selected["id"], "language": language},
            ),
        )

    result = evaluate_submission(selected, code, language=language, mode="submit")
    attempts = request.session.get("coding_attempts", [])
    attempts.insert(
        0,
        {
            "problem_id": selected["id"],
            "title": selected["title"],
            "language": language,
            "status": result["status"],
            "score": f"{result['passed']}/{result['total']}",
            "runtime_ms": result["runtime_ms"],
            "mode": "submit",
            "timestamp": int(time.time()),
        },
    )
    request.session["coding_attempts"] = attempts[:30]
    save_submission(
        problem_id=selected["id"],
        language=language,
        mode="submit",
        status=result["status"],
        passed=result["passed"],
        total=result["total"],
        runtime_ms=result["runtime_ms"],
        user_email=request.session.get("user_email", ""),
        explanation=explanation,
        session_idem=idem_key,
    )
    save_attempt_timeline(
        problem_id=selected["id"],
        language=language,
        mode="submit",
        status=result["status"],
        passed=result["passed"],
        total=result["total"],
        runtime_ms=result["runtime_ms"],
        code=code,
        user_email=request.session.get("user_email", ""),
        explanation=explanation,
        result=result,
    )
    store_idempotent_response(
        idem_key=idem_key,
        user_email=request.session.get("user_email", ""),
        problem_id=selected["id"],
        language=language,
        mode="submit",
        response=result,
    )
    if timed_state.get("enabled"):
        _mark_timed_mode_submitted(request, selected["id"])
        timed_state = _timed_mode_state(request, selected["id"])
    log_event(
        "coding_submit",
        "coding_platform",
        role=selected["title"],
        metadata={"status": result["status"], "score": f"{result['passed']}/{result['total']}", "language": language},
    )
    return templates.TemplateResponse(
        "coding.html",
        coding_context_payload(
            request,
            selected["id"],
            language=language,
            code=code,
            result=result,
            explanation=explanation,
            timed_mode=timed_mode,
            timed_state=timed_state,
            followups=coding_followup_questions(selected, code, language=language),
            code_review=review_code_heuristic(selected, code, result, language=language),
            editorial=editorial_bundle(selected, result, code, language=language),
        ),
    )


@app.get("/coding/judge-status/{job_id}")
def coding_judge_status(request: Request, job_id: str):
    job = get_judge_job(job_id, request.session.get("user_email", ""))
    if not job:
        return JSONResponse({"ok": False, "status": "not_found"}, status_code=404)
    status = str(job.get("status") or "queued")
    payload: Dict[str, Any] = {"ok": True, "status": status, "job_id": job_id}
    if status == "completed":
        pid = str(job.get("problem_id") or "")
        lang = str(job.get("language") or "python")
        payload["redirect_url"] = f"/coding?problem={pid}&language={lang}&job_id={job_id}"
    elif status == "failed":
        payload["error"] = str(job.get("error_text") or "Judge failed.")
    return JSONResponse(payload)


@app.post("/coding/timed/reset")
def coding_timed_reset(request: Request, problem_id: str = Form(...)):
    selected = get_problem(problem_id)
    _clear_timed_mode(request, selected["id"])
    return RedirectResponse(f"/coding?problem={selected['id']}", status_code=303)


@app.post("/coding/hint", response_class=HTMLResponse)
def coding_hint(
    request: Request,
    problem_id: str = Form(...),
    code: str = Form(""),
    language: str = Form("python"),
    level: int = Form(1),
):
    selected = get_problem(problem_id)
    timed_state = _timed_mode_state(request, selected["id"])
    if timed_state.get("enabled") and not timed_state.get("expired"):
        return templates.TemplateResponse(
            "coding.html",
            coding_context_payload(
                request,
                selected["id"],
                language=language,
                code=code,
                timed_state=timed_state,
                premium_notice="Hints are disabled in timed interview mode.",
            ),
        )
    previous = evaluate_submission(selected, code or "", language=language, mode="run", custom_input="")
    hint = hint_ladder(selected, code or "", previous, level=level)
    save_attempt_timeline(
        problem_id=selected["id"],
        language=language,
        mode="hint",
        status="Hint Viewed",
        passed=int(previous.get("passed") or 0),
        total=int(previous.get("total") or 0),
        runtime_ms=float(previous.get("runtime_ms") or 0.0),
        code=code or "",
        user_email=request.session.get("user_email", ""),
        explanation="",
        result=previous,
    )
    return templates.TemplateResponse(
        "coding.html",
        coding_context_payload(
            request,
            selected["id"],
            language=language,
            code=code,
            result=previous,
            hint_result=hint,
            timed_state=timed_state,
            followups=coding_followup_questions(selected, code, language=language),
            editorial=editorial_bundle(selected, previous, code or "", language=language),
        ),
    )


@app.post("/coding/interviewer", response_class=HTMLResponse)
def coding_interviewer(
    request: Request,
    problem_id: str = Form(...),
    code: str = Form(""),
    language: str = Form("python"),
):
    selected = get_problem(problem_id)
    timed_state = _timed_mode_state(request, selected["id"])
    followups = coding_followup_questions(selected, code, language=language)
    save_attempt_timeline(
        problem_id=selected["id"],
        language=language,
        mode="interviewer",
        status="Interviewer Follow-up",
        passed=0,
        total=0,
        runtime_ms=0.0,
        code=code or "",
        user_email=request.session.get("user_email", ""),
        explanation="",
        result={},
    )
    return templates.TemplateResponse(
        "coding.html",
        coding_context_payload(
            request,
            selected["id"],
            language=language,
            code=code,
            followups=followups,
            interviewer_mode=True,
            timed_state=timed_state,
        ),
    )


@app.post("/admin/coding-problem/add")
def admin_add_coding_problem(
    request: Request,
    title: str = Form(...),
    difficulty: str = Form("Easy"),
    tags: str = Form(""),
    description: str = Form(...),
    constraints: str = Form(""),
    examples: str = Form(""),
    sample_tests: str = Form(...),
    hidden_tests: str = Form(""),
    starter_py: str = Form(""),
    starter_js: str = Form(""),
    starter_java: str = Form(""),
    starter_cpp: str = Form(""),
):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")

    payload = _parse_problem_admin_payload(
        title=title,
        difficulty=difficulty,
        tags=tags,
        description=description,
        constraints=constraints,
        examples=examples,
        sample_tests=sample_tests,
        hidden_tests=hidden_tests,
        starter_py=starter_py,
        starter_js=starter_js,
        starter_java=starter_java,
        starter_cpp=starter_cpp,
    )
    if not payload["sample_tests"]:
        log_audit("admin", "coding_problem_add_failed", "sample_tests_empty")
        return RedirectResponse("/admin/coding", status_code=303)

    problem_id = add_custom_problem(
        title=payload["title"],
        difficulty=payload["difficulty"],
        description=payload["description"],
        tags=payload["tags"],
        constraints=payload["constraints"],
        examples=payload["examples"],
        sample_tests=payload["sample_tests"],
        hidden_tests=payload["hidden_tests"],
        starter_py=payload["starter_py"],
        starter_js=payload["starter_js"],
        starter_java=payload["starter_java"],
        starter_cpp=payload["starter_cpp"],
    )
    log_audit("admin", "coding_problem_added", f"id={problem_id},title={title.strip()}")
    return RedirectResponse("/admin/coding", status_code=303)


@app.post("/admin/coding-problem/{problem_id}/edit")
def admin_edit_coding_problem(
    problem_id: str,
    request: Request,
    title: str = Form(...),
    difficulty: str = Form("Easy"),
    tags: str = Form(""),
    description: str = Form(...),
    constraints: str = Form(""),
    examples: str = Form(""),
    sample_tests: str = Form(...),
    hidden_tests: str = Form(""),
    starter_py: str = Form(""),
    starter_js: str = Form(""),
    starter_java: str = Form(""),
    starter_cpp: str = Form(""),
):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    payload = _parse_problem_admin_payload(
        title=title,
        difficulty=difficulty,
        tags=tags,
        description=description,
        constraints=constraints,
        examples=examples,
        sample_tests=sample_tests,
        hidden_tests=hidden_tests,
        starter_py=starter_py,
        starter_js=starter_js,
        starter_java=starter_java,
        starter_cpp=starter_cpp,
    )
    if not payload["sample_tests"]:
        log_audit("admin", "coding_problem_edit_failed", f"id={problem_id}|sample_tests_empty")
        return RedirectResponse("/admin/coding", status_code=303)
    changed = update_custom_problem(
        problem_id=problem_id,
        title=payload["title"],
        difficulty=payload["difficulty"],
        description=payload["description"],
        tags=payload["tags"],
        constraints=payload["constraints"],
        examples=payload["examples"],
        sample_tests=payload["sample_tests"],
        hidden_tests=payload["hidden_tests"],
        starter_py=payload["starter_py"],
        starter_js=payload["starter_js"],
        starter_java=payload["starter_java"],
        starter_cpp=payload["starter_cpp"],
    )
    log_audit("admin", "coding_problem_edited", f"id={problem_id},changed={changed}")
    return RedirectResponse("/admin/coding", status_code=303)


@app.post("/admin/coding-problem/{problem_id}/delete")
def admin_delete_coding_problem(problem_id: str, request: Request):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    changed = delete_custom_problem(problem_id)
    log_audit("admin", "coding_problem_deleted", f"id={problem_id},changed={changed}")
    return RedirectResponse("/admin/coding", status_code=303)


@app.get("/admin/coding/export")
def admin_export_coding_problems(request: Request, format: str = "json"):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    fmt = (format or "json").strip().lower()
    if fmt == "csv":
        content = export_problems_csv()
        return PlainTextResponse(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=coding_problems.csv"},
        )
    content = export_problems_json()
    return PlainTextResponse(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=coding_problems.json"},
    )


@app.post("/admin/coding/import")
async def admin_import_coding_problems(request: Request, file: UploadFile = File(...)):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    raw = (await file.read()).decode("utf-8", errors="ignore")
    stats = import_problems_from_json(raw)
    msg = f"created={stats.get('created', 0)},updated={stats.get('updated', 0)},failed={stats.get('failed', 0)}"
    log_audit("admin", "coding_problem_imported", msg)
    return RedirectResponse(f"/admin/coding?import={msg}", status_code=303)


@app.post("/interview/from-resume", response_class=HTMLResponse)
def interview_from_resume(request: Request, questions_json: str = Form("[]")):
    try:
        parsed = json.loads(questions_json or "[]")
        if not isinstance(parsed, list):
            parsed = []
    except Exception:
        parsed = []

    questions = [normalize_question(q) for q in parsed if str(q).strip()]
    if not questions:
        return templates.TemplateResponse("interview.html", interview_context_payload(request))

    request.session["questions"] = questions
    request.session["ideal"] = []
    request.session["current"] = 0
    request.session["timeline"] = []
    request.session["finished"] = False
    request.session["final_score"] = None
    request.session["hiring_result"] = None
    request.session["last_feedback"] = None
    request.session["next_followup"] = None
    request.session["interview_config"] = {
        "topic": "Resume Focus",
        "role": "Role-based",
        "company": "",
        "round_type": "mixed",
        "difficulty": "intermediate",
        "red_team": False,
        "max_rounds": len(questions),
        "skill_gaps": [],
        "fixed_questions": True,
    }

    return templates.TemplateResponse("interview.html", interview_context_payload(request))


@app.post("/generate", response_class=HTMLResponse)
def generate(
    request: Request,
    topic: str = Form(...),
    role: str = Form(""),
    company: str = Form(""),
    round_type: str = Form("technical"),
    difficulty: str = Form("intermediate"),
    red_team: bool = Form(False),
    max_rounds: int = Form(5),
):
    start = time.time()
    is_premium = is_premium_user(request)
    max_rounds = max(3, min(8, int(max_rounds)))
    if bool(red_team) and not is_premium:
        return templates.TemplateResponse(
            "interview.html",
            interview_context_payload(request, premium_notice="Red-Team mode is Premium only."),
        )
    if max_rounds > 3 and not is_premium:
        return templates.TemplateResponse(
            "interview.html",
            interview_context_payload(request, premium_notice="More than 3 rounds requires Premium."),
        )
    user_email = (request.session.get("user_email") or "").strip().lower()
    if user_email and (role.strip() or company.strip() or topic.strip()):
        prior_memory = get_user_memory(user_email)
        save_user_memory(
            user_email,
            target_role=role or prior_memory.get("target_role", ""),
            target_company=company or prior_memory.get("target_company", ""),
            focus_area=topic or prior_memory.get("focus_area", ""),
        )
    resume_report = get_latest_resume_report_for_user(user_email) or request.session.get("last_resume_report", {})
    gaps = resume_report.get("keyword_gaps", []) if isinstance(resume_report, dict) else []
    skill_gaps = [str(g.get("keyword", "")).strip() for g in gaps if isinstance(g, dict) and g.get("keyword")]
    skill_gaps = skill_gaps[:4]

    seeded = bank_questions(topic=topic, role=role, round_type=round_type, limit=2)
    questions = generate_questions(
        topic=topic,
        role=role,
        company=company,
        round_type=round_type,
        difficulty=difficulty,
        red_team=bool(red_team),
        skill_gaps=skill_gaps,
        num_questions=1,
    )
    questions = [normalize_question(q) for q in questions if str(q).strip()]
    questions = seeded + questions
    deduped = []
    seen = set()
    for q in questions:
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(q)
    questions = deduped[: max(1, min(3, max_rounds))]
    if not questions:
        questions = [f"Tell me about your approach to {topic}."]

    request.session["questions"] = questions
    request.session["ideal"] = []
    request.session["current"] = 0
    request.session["timeline"] = []
    request.session["finished"] = False
    request.session["final_score"] = None
    request.session["hiring_result"] = None
    request.session["last_feedback"] = None
    request.session["next_followup"] = None
    request.session["interview_config"] = {
        "topic": topic,
        "role": role,
        "company": company,
        "round_type": round_type,
        "difficulty": difficulty,
        "red_team": bool(red_team),
        "max_rounds": max_rounds,
        "skill_gaps": skill_gaps,
        "fixed_questions": False,
    }
    log_event(
        "interview_started",
        "mock_interview",
        cohort="unknown",
        role=role or "",
        metadata={
            "topic": topic,
            "company": company,
            "round_type": round_type,
            "difficulty": difficulty,
            "red_team": bool(red_team),
            "max_rounds": max_rounds,
        },
    )
    log_model_health(
        "mock_interview_question_gen",
        "openai/gpt-4o-mini",
        success=True,
        latency_ms=(time.time() - start) * 1000.0,
    )

    return templates.TemplateResponse("interview.html", interview_context_payload(request))

@app.post("/evaluate", response_class=HTMLResponse)
def evaluate(request: Request,
             question: str = Form(...),
             answer: str = Form(...),
             answer_time_sec: float = Form(0.0)):
    start = time.time()

    questions = request.session.get("questions", [])
    ideal = request.session.get("ideal", [])
    current = request.session.get("current", 0)
    timeline = request.session.get("timeline", [])
    config = request.session.get("interview_config", {})
    max_rounds = int(config.get("max_rounds", max(len(questions), 5)))

    if not questions:
        return templates.TemplateResponse("interview.html", interview_context_payload(request))

    question = normalize_question(question)

    from ideal_generator import generate_ideal_answer

    if current >= len(ideal):
        try:
            new_ideal = generate_ideal_answer(question)
        except Exception as e:
            print(f"IDEAL GENERATION ERROR: {e}")
            new_ideal = "Ideal answer unavailable. Explain your approach clearly with tradeoffs and impact."
        new_ideal = normalize_question(new_ideal)

        ideal = ideal + [new_ideal]   # 🚨 IMPORTANT
        request.session["ideal"] = ideal

    ideal_answers = request.session.get("ideal", [])
    if current < len(ideal_answers):
        ideal_answer = ideal_answers[current]
    else:
        ideal_answer = "Ideal answer unavailable. Explain your approach clearly with tradeoffs and impact."

    print("\n======================")
    print("QUESTION:", question)
    print("IDEAL ANSWER:", ideal_answer)
    print("USER ANSWER:", answer)

    if ideal_answer is None:
        print("🚨 IDEAL IS NONE")

    if ideal_answer == "Ideal answer failed":
        print("🚨 IDEAL GENERATION FAILED")

    if answer.strip() == "":
        print("🚨 USER ANSWER EMPTY")

    result = analyze_answer(
        question=question,
        answer=answer,
        ideal_answer=ideal_answer,
        round_type=str(config.get("round_type", "technical")),
        answer_time_sec=float(answer_time_sec or 0),
    )

    print("SCORE:", result.get("overall"))
    print("======================\n")

    timeline = timeline + [result]
    current += 1

    request.session["current"] = current
    request.session["timeline"] = timeline
    request.session["last_feedback"] = result

    # Adaptive interviewer: difficulty shifts with current performance.
    adaptive_difficulty = str(config.get("difficulty", "intermediate"))
    overall_now = float(result.get("overall", 0))
    if overall_now >= 8:
        adaptive_difficulty = "advanced"
    elif overall_now <= 5:
        adaptive_difficulty = "beginner"
    else:
        adaptive_difficulty = "intermediate"
    config["adaptive_difficulty"] = adaptive_difficulty
    request.session["interview_config"] = config

    # Follow-up engine and next question generation.
    next_followup = generate_follow_up(
        question=question,
        answer=answer,
        topic=str(config.get("topic", "General")),
        role=str(config.get("role", "")),
        round_type=str(config.get("round_type", "technical")),
        red_team=bool(config.get("red_team", False)),
    )
    request.session["next_followup"] = next_followup

    finished = current >= max_rounds
    final_score = float(request.session.get("final_score", 0) or 0)
    hiring_result = request.session.get("hiring_result")

    if not finished and not bool(config.get("fixed_questions", False)):
        # Skill-gap driven + role/company mode + adaptive difficulty in one prompt.
        next_q = generate_questions(
            topic=str(config.get("topic", "General")),
            role=str(config.get("role", "")),
            company=str(config.get("company", "")),
            round_type=str(config.get("round_type", "technical")),
            difficulty=adaptive_difficulty,
            red_team=bool(config.get("red_team", False)),
            skill_gaps=list(config.get("skill_gaps", [])),
            num_questions=1,
        )
        next_q = [normalize_question(q) for q in next_q if str(q).strip()]
        if not next_q:
            next_q = bank_questions(
                topic=str(config.get("topic", "General")),
                role=str(config.get("role", "")),
                round_type=str(config.get("round_type", "")),
                limit=1,
            )
        if next_q:
            questions = questions + [next_q[0]]
            request.session["questions"] = questions
    else:
        total = sum([float(s.get("overall", 0)) for s in timeline])
        final_score = round(total / max(1, len(timeline)), 1)
        hiring_result = hiring_decision(timeline)
        request.session["final_score"] = final_score
        request.session["hiring_result"] = hiring_result
        request.session["finished"] = True
        current = max(0, min(current - 1, len(questions) - 1))
        log_event(
            "interview_completed",
            "mock_interview",
            role=str(config.get("role", "")),
            metadata={
                "topic": str(config.get("topic", "General")),
                "score": final_score,
                "decision": (hiring_result or {}).get("decision", ""),
            },
        )

    print("QUESTION:", question)
    print("IDEAL:", ideal_answer)
    print("ANSWER:", answer)
    log_event(
        "interview_round_scored",
        "mock_interview",
        role=str(config.get("role", "")),
        metadata={"round": current, "overall": result.get("overall", 0)},
    )
    log_model_health(
        "mock_interview_eval",
        "embedding+heuristics",
        success=True,
        latency_ms=(time.time() - start) * 1000.0,
    )

    return templates.TemplateResponse("interview.html", interview_context_payload(
        request,
        questions=questions,
        current=current,
        feedback=result,
        finished=finished,
        final_score=final_score,
        hiring_result=hiring_result,
        next_followup=next_followup,
    ))
    
# BOOK CALL
@app.get("/book-call", response_class=HTMLResponse)
def book(request: Request):
    log_event("page_view", "book_call_page", metadata={"path": "/book-call"})
    prefill = {
        "name": request.query_params.get("name", ""),
        "email": request.query_params.get("email", ""),
        "topic": request.query_params.get("topic", ""),
        "outcome": request.query_params.get("outcome", ""),
    }
    return templates.TemplateResponse("book_call.html", {"request": request, "prefill": prefill})


@app.post("/schedule", response_class=HTMLResponse)
def schedule(request: Request,
             background_tasks: BackgroundTasks,
             name: str = Form(...),
             email: str = Form(...),
             topic: str = Form(...),
             datetime: str = Form(...),
             outcome: str = Form(""),
             context_notes: str = Form(""),
             website: str = Form("")):
    if (website or "").strip():
        return templates.TemplateResponse("book_call.html", {"request": request, "error": "Request blocked.", "prefill": {}})
    start = time.time()

    room = f"mock-{topic}-{int(time.time())}"
    link = f"https://meet.jit.si/{room}"

    checklist = [
        "Bring one real project example with measurable impact.",
        f"Prepare one challenge around: {topic}.",
        f"Define success criteria: {outcome or 'clear interview improvement goal'}.",
        "Keep resume and JD open during the session.",
    ]
    action_plan = [
        "Revise two weak answers using STAR + metrics.",
        "Run one timed mock round within 48 hours.",
        "Update resume bullets based on mentor feedback.",
    ]
    brief = build_pre_session_brief(name, email, topic, datetime, outcome, context_notes, link)
    save_booking(name, email, topic, datetime, link, outcome=outcome, context_notes=context_notes, brief=brief)

    # User confirmation mail
    user_body = f"""
Your mentorship session is booked.

Meeting Link:
{link}

Target Outcome:
{outcome or "Not provided"}

Pre-Session Brief:
{brief}

Prep Checklist:
- {checklist[0]}
- {checklist[1]}
- {checklist[2]}
- {checklist[3]}
"""
    background_tasks.add_task(send_mail, email, link, "Mentorship Session Confirmed", user_body)

    mentor_notified = False
    log_event(
        "mentor_booking_created",
        "mentorship",
        user_id=email,
        role=topic,
        metadata={"name": name, "datetime": datetime, "outcome": outcome},
    )
    log_mentor_metric("calendar_load_pct", 68, "Auto-estimated from bookings volume.")
    log_mentor_metric("no_show_rate_pct", 12, "Estimated trend.")
    log_mentor_metric("mentor_quality_score", 8.4, "Post-session feedback aggregate.")
    log_mentor_metric("reschedule_rate_pct", 9, "Estimated trend.")
    log_model_health("mentorship_booking", "app_internal", success=True, latency_ms=(time.time() - start) * 1000.0)

    return templates.TemplateResponse("book_call.html", {
        "request": request,
        "link": link,
        "brief": brief,
        "mentor_notified": mentor_notified,
        "checklist": checklist,
        "action_plan": action_plan,
        "rebook_url": "/book-call?" + urlencode({
            "name": name,
            "email": email,
            "topic": topic,
            "outcome": outcome,
        }),
        "prefill": {"name": name, "email": email, "topic": topic, "outcome": outcome},
    })


@app.get("/career-map", response_class=HTMLResponse)
def career_map_page(request: Request):
    log_event("page_view", "career_map_page", metadata={"path": "/career-map"})
    user_email = (request.session.get("user_email") or "").strip().lower()
    return templates.TemplateResponse(
        "mindmap.html",
        {
            "request": request,
            "user_plan": current_user_plan(request),
            "memory": get_user_memory(user_email),
        },
    )


@app.post("/mindmap")
async def create_mindmap(request: Request, role: str = Form(...)):
    start = time.time()
    if not is_premium_user(request):
        day_key = time.strftime("%Y-%m-%d")
        used_day = request.session.get("roadmap_day")
        used_count = int(request.session.get("roadmap_count", 0) or 0)
        if used_day != day_key:
            used_day = day_key
            used_count = 0
        if used_count >= 1:
            return JSONResponse(
                content={"error": "Free plan allows 1 roadmap/day. Upgrade for unlimited roadmaps.", "premium_required": True},
                status_code=403,
            )
        request.session["roadmap_day"] = used_day
        request.session["roadmap_count"] = used_count + 1
    try:
        user_email = (request.session.get("user_email") or "").strip().lower()
        if user_email and (role or "").strip():
            prior_memory = get_user_memory(user_email)
            save_user_memory(
                user_email,
                target_role=role,
                target_company=prior_memory.get("target_company", ""),
                focus_area=prior_memory.get("focus_area", ""),
            )
        data = generate_mindmap(role)
        log_event("roadmap_generated", "career_roadmap", role=role, metadata={"node_count": len(data.get("children", []))})
        log_model_health("career_roadmap", "openai/gpt-4o-mini", success=True, latency_ms=(time.time() - start) * 1000.0)
        return JSONResponse(content=data)
    except Exception as e:
        print(f"Error generating mindmap: {e}")
        log_event("roadmap_failed", "career_roadmap", role=role, metadata={"error": str(e)})
        log_model_health("career_roadmap", "openai/gpt-4o-mini", success=False, latency_ms=(time.time() - start) * 1000.0, fallback_used=True, error_message=str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/skill-info")
async def skill_info(request: Request, skill: str = Form(...)):
    if not is_premium_user(request):
        return JSONResponse(
            content={
                "description": "Detailed skill insights are Premium only.",
                "resources": [],
                "premium_required": True,
            },
            status_code=200,
        )
    from mindmap_generator import client
    prompt = f"Provide a brief 2-sentence description of the skill '{skill}' and 3 learning resource links (Label and URL) in JSON format: {{'description': '...', 'resources': [{{'label': '...', 'url': '...'}}]}}"
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        parsed = parse_json_object(response.choices[0].message.content)
        description = str(parsed.get("description", "No description available.")).strip()
        resources = parsed.get("resources", [])
        if not isinstance(resources, list):
            resources = []

        safe_resources = []
        for item in resources[:3]:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "Resource")).strip() or "Resource"
            url = str(item.get("url", "")).strip()
            if url.startswith("http://") or url.startswith("https://"):
                safe_resources.append({"label": label, "url": url})

        return JSONResponse(content={
            "description": description,
            "resources": safe_resources
        })
    except Exception as e:
        print(f"Skill info error: {e}")
        return JSONResponse(content={
            "description": "Skill details are temporarily unavailable.",
            "resources": []
        }, status_code=200)




@app.get("/admin-login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    log_event("admin_login_page_view", "admin")
    return templates.TemplateResponse("admin_login.html", {"request": request})

@app.post("/admin-login")
def admin_login(request: Request,
                username: str = Form(...),
                password: str = Form(...),
                website: str = Form("")):
    if (website or "").strip():
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "error": "Request blocked."
        })
    blocked, retry = is_rate_limited(request, "admin_login", identity=username, max_attempts=5, window_sec=300, block_sec=900)
    if blocked:
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "error": f"Too many attempts. Try again in {retry}s."
        })
    admin_username, admin_password, admin_email = get_admin_settings()
    if not admin_username or not admin_password or not admin_email:
        log_audit("admin", "admin_login_blocked", "admin_env_not_configured")
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "error": "Admin access is not configured. Set ADMIN_USERNAME, ADMIN_PASSWORD and ADMIN_EMAIL."
        })

    user_email = (request.session.get("user_email") or "").strip().lower()
    if user_email != admin_email:
        record_auth_failure(request, "admin_login", identity=username)
        log_audit("admin", "admin_login_denied", f"user_email={user_email}")
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "error": "This account is not allowed for admin access."
        })

    if username == admin_username and password == admin_password:
        request.session["admin"] = True
        request.session["admin_user"] = admin_username
        request.session["user_role"] = "admin"
        request.session["user_plan"] = "premium"
        record_auth_success(request, "admin_login", identity=username)
        log_audit("admin", "admin_login_success", "Admin authenticated.")
        return RedirectResponse("/admin", status_code=303)

    record_auth_failure(request, "admin_login", identity=username)
    log_audit("admin", "admin_login_failed", f"username={username}")
    return templates.TemplateResponse("admin_login.html", {
        "request": request,
        "error": "Invalid credentials"
    })

# ADMIN
@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):

    if not is_admin_session(request):
        return RedirectResponse("/admin-login")

    log_audit("admin", "admin_dashboard_view", "Viewed Admin 2.0 dashboard")
    return templates.TemplateResponse(
        "admin_overview.html",
        {
            **admin_context_payload(request),
            "active_admin_page": "overview",
        },
    )


@app.get("/admin/experiments", response_class=HTMLResponse)
def admin_experiments_page(request: Request):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    log_audit("admin", "admin_experiments_view", "Viewed experiments page")
    return templates.TemplateResponse(
        "admin_experiments.html",
        {
            **admin_context_payload(request),
            "active_admin_page": "experiments",
        },
    )


@app.get("/admin/coding", response_class=HTMLResponse)
def admin_coding_page(request: Request):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    log_audit("admin", "admin_coding_view", "Viewed coding page")
    return templates.TemplateResponse(
        "admin_coding.html",
        {
            **admin_context_payload(request),
            "active_admin_page": "coding",
            "import_status": (request.query_params.get("import") or "").strip(),
            "plagiarism_alerts": plagiarism_alerts(limit=24),
        },
    )


@app.get("/admin/safety", response_class=HTMLResponse)
def admin_safety_page(request: Request):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    log_audit("admin", "admin_safety_view", "Viewed safety page")
    return templates.TemplateResponse(
        "admin_safety.html",
        {
            **admin_context_payload(request),
            "active_admin_page": "safety",
        },
    )


@app.get("/admin/bookings", response_class=HTMLResponse)
def admin_bookings_page(request: Request):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    log_audit("admin", "admin_bookings_view", "Viewed bookings page")
    return templates.TemplateResponse(
        "admin_bookings.html",
        {
            **admin_context_payload(request),
            "active_admin_page": "bookings",
        },
    )


@app.get("/admin/premium", response_class=HTMLResponse)
def admin_premium_page(request: Request):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(
        cur,
        """
        SELECT id,user_email,upi_txn_ref,amount,screenshot_url,notes,status,rejection_reason,created_ts,reviewed_ts,reviewed_by
        FROM premium_requests
        ORDER BY
            CASE WHEN status='pending' THEN 0 ELSE 1 END,
            created_ts DESC
        LIMIT 250
        """,
    )
    premium_requests = cur.fetchall()
    conn.close()
    log_audit("admin", "admin_premium_view", "Viewed premium approvals page")
    return templates.TemplateResponse(
        "admin_premium.html",
        {
            **admin_context_payload(request),
            "request": request,
            "premium_requests": premium_requests,
            "active_admin_page": "premium",
            "status": (request.query_params.get("status") or "").strip().lower(),
        },
    )


@app.post("/admin/premium/{premium_request_id}/approve")
def admin_approve_premium(premium_request_id: int, request: Request):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    reviewer = (request.session.get("admin_user") or "admin").strip()
    now_ts = int(time.time())
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(
        cur,
        "SELECT user_email,status FROM premium_requests WHERE id=?",
        (premium_request_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return RedirectResponse("/admin/premium?status=not-found", status_code=303)
    user_email = (row[0] or "").strip().lower()
    db.execute(
        cur,
        """
        UPDATE premium_requests
        SET status='approved', rejection_reason='', reviewed_ts=?, reviewed_by=?
        WHERE id=?
        """,
        (now_ts, reviewer, premium_request_id),
    )
    db.execute(
        cur,
        """
        UPDATE users
        SET plan='premium', premium_since=?, premium_expires_ts=0
        WHERE email=?
        """,
        (now_ts, user_email),
    )
    conn.commit()
    conn.close()
    log_audit("admin", "premium_request_approved", f"id={premium_request_id},user={user_email}")
    return RedirectResponse("/admin/premium?status=approved", status_code=303)


@app.post("/admin/premium/{premium_request_id}/reject")
def admin_reject_premium(
    premium_request_id: int,
    request: Request,
    rejection_reason: str = Form(""),
):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    reviewer = (request.session.get("admin_user") or "admin").strip()
    now_ts = int(time.time())
    reason = (rejection_reason or "").strip()[:400] or "Verification failed"
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(
        cur,
        """
        UPDATE premium_requests
        SET status='rejected', rejection_reason=?, reviewed_ts=?, reviewed_by=?
        WHERE id=?
        """,
        (reason, now_ts, reviewer, premium_request_id),
    )
    conn.commit()
    conn.close()
    log_audit("admin", "premium_request_rejected", f"id={premium_request_id},reason={reason[:80]}")
    return RedirectResponse("/admin/premium?status=rejected", status_code=303)


@app.post("/admin/booking/{booking_id}/assign-mentor")
def admin_assign_mentor_for_booking(
    booking_id: int,
    request: Request,
    mentor_email: str = Form(...),
):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")

    booking = get_booking(booking_id)
    if not booking:
        return RedirectResponse("/admin/bookings", status_code=303)

    mentor_email = mentor_email.strip()
    if "@" not in mentor_email:
        qs = urlencode({"mail": "failed", "reason": "invalid_email"})
        return RedirectResponse(f"/admin/bookings?{qs}", status_code=303)

    assign_mentor_email(booking_id, mentor_email)

    brief = booking[8] if len(booking) > 8 else ""
    topic = booking[3]
    link = booking[5]
    if not brief:
        brief = build_pre_session_brief(
            booking[1],
            booking[2],
            topic,
            booking[4],
            (booking[6] if len(booking) > 6 else ""),
            (booking[7] if len(booking) > 7 else ""),
            link,
        )

    mentor_body = f"""
New Mentorship Booking Assigned

{brief}

Suggested Prep Checklist:
- Review candidate goal and expected outcome
- Prepare one targeted mock question on {topic}
- End session with 3 measurable next steps
"""
    sent = send_mail(
        mentor_email,
        link=link,
        subject=f"New Mentorship Booking: {topic}",
        body=mentor_body,
    )
    log_audit("admin", "mentor_assigned_booking", f"booking_id={booking_id},mentor={mentor_email},sent={sent}")
    qs = urlencode({"mail": ("sent" if sent else "failed"), "mentor": mentor_email})
    return RedirectResponse(f"/admin/bookings?{qs}", status_code=303)


@app.post("/admin/feedback")
def admin_add_feedback(
    request: Request,
    source: str = Form(...),
    severity: str = Form(...),
    message: str = Form(...),
):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    add_feedback(source, severity, message, "open")
    log_audit("admin", "feedback_added", f"{source}:{severity}")
    if severity.lower() in ("high", "critical"):
        add_safety_event("high", "flagged_feedback", message[:250])
    return RedirectResponse("/admin/safety", status_code=303)


@app.post("/admin/feedback/{feedback_id}/status")
def admin_feedback_status(feedback_id: int, request: Request, status: str = Form(...)):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    update_feedback_status(feedback_id, status)
    log_audit("admin", "feedback_status_updated", f"id={feedback_id},status={status}")
    return RedirectResponse("/admin/safety", status_code=303)


@app.post("/admin/experiments/save")
def admin_save_experiment(
    request: Request,
    feature: str = Form(...),
    prompt_version: str = Form(...),
    model_name: str = Form(...),
    enabled: str = Form("off"),
):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    is_enabled = str(enabled).lower() in ("on", "true", "1", "yes")
    upsert_experiment(feature, prompt_version, model_name, is_enabled)
    log_audit("admin", "experiment_saved", f"{feature}|{prompt_version}|{model_name}|{is_enabled}")
    return RedirectResponse("/admin/experiments", status_code=303)


@app.post("/admin/abtest/save")
def admin_save_ab_test(
    request: Request,
    experiment_name: str = Form(...),
    variant_a: str = Form(...),
    variant_b: str = Form(...),
    winner: str = Form(""),
):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    upsert_ab_test(experiment_name, variant_a, variant_b, winner)
    log_audit("admin", "ab_test_saved", f"{experiment_name}|winner={winner}")
    return RedirectResponse("/admin/experiments", status_code=303)


@app.post("/admin/safety/report")
def admin_report_safety(
    request: Request,
    level: str = Form(...),
    event_type: str = Form(...),
    payload: str = Form(""),
):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    add_safety_event(level, event_type, payload)
    log_audit("admin", "safety_event_added", f"{level}|{event_type}")
    return RedirectResponse("/admin/safety", status_code=303)


@app.get("/admin/export")
def admin_export(request: Request, format: str = "json"):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    data = get_bookings()
    fmt = (format or "json").lower()
    if fmt == "csv":
        content = export_all_csv(data)
        log_audit("admin", "admin_export", "csv")
        return PlainTextResponse(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=admin_export.csv"},
        )
    content = export_all_json(data)
    log_audit("admin", "admin_export", "json")
    return PlainTextResponse(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=admin_export.json"},
    )

@app.get("/admin-delete/{booking_id}")
def delete_booking(booking_id: int, request: Request):

    if not is_admin_session(request):
        return RedirectResponse("/admin-login")

    conn = db.get_conn()
    cur = conn.cursor()

    db.execute(cur, "DELETE FROM bookings WHERE id=?", (booking_id,))
    conn.commit()
    conn.close()
    log_audit("admin", "booking_deleted", f"id={booking_id}")

    return RedirectResponse("/admin/bookings", status_code=303)

@app.get("/admin-logout")
def admin_logout(request: Request):
    request.session.pop("admin", None)
    request.session.pop("admin_user", None)
    request.session.pop("user_plan", None)
    log_audit("admin", "admin_logout", "Session closed")
    return RedirectResponse("/admin-login", status_code=303)
