from fastapi import FastAPI, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from resume_parser import extract_text
from scoring import score_resume
from interview_engine import generate_questions, generate_follow_up, generate_lifeline_hints
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
TRUSTED_HOSTS = [h.strip() for h in (os.getenv("TRUSTED_HOSTS") or "localhost,127.0.0.1,testserver").split(",") if h.strip()] + ["*.onrender.com"]
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

import requests
from bs4 import BeautifulSoup

def scrape_job_link(url: str) -> str:
    if not url:
        return ""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        for script_or_style in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            script_or_style.decompose()

        text = soup.get_text(separator="\n")
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)
        
        return text[:15000] # Limit scraped context to 15k chars to prevent prompt blowouts
    except Exception as e:
        logger.warning("Scraping failed for %s: %s", url, e)
        return ""
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


