from .ai_client import call_ai_with_fallback
import json
from urllib.parse import urlparse
import os
import time
import secrets
import hashlib
import hmac
from typing import Any, Dict

from .ai_client import call_ai_with_fallback, call_ai_chat
from .validators import (
    parse_json_object, 
    validate_parsed, 
    clamp_score, 
    safe_list,
    _timed_session_key,
    _timed_mode_state,
    _readiness_from_summary,
    _daily_goal_from_attempts,
    validate_password_strength
)

APP_ENV = (os.getenv("APP_ENV") or "development").strip().lower()
CSRF_STRICT = (os.getenv("CSRF_STRICT") or "false").strip().lower() in ("1", "true", "yes", "on")

_TIMED_ALLOWED = {"35", "45"}


def _same_origin(request) -> bool:
    host = (request.headers.get("host") or "").strip().lower()
    source = (request.headers.get("origin") or request.headers.get("referer") or "").strip()
    if not source: return APP_ENV != "production" or not CSRF_STRICT
    try: return urlparse(source).netloc.lower() == host
    except: return False

__all__ = ["call_ai_with_fallback", "parse_json_object", "_same_origin", "validate_password_strength", "hash_password", "verify_password", "is_rate_limited", "record_auth_failure", "record_auth_success", "_timed_mode_state", "_readiness_from_summary", "_daily_goal_from_attempts"]


def _auth_key(request, action: str, identity: str = "") -> str:
    ip = ""
    try: ip = request.client.host if request.client else ""
    except: ip = ""
    return f"{action}:{(identity or '').strip().lower()}:{ip}"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt.encode("utf-8"), 200_000).hex()
    return f"pbkdf2_sha256$200000${salt}${digest}"

def verify_password(stored: str, password: str) -> bool:
    value = (stored or "").strip()
    if value.startswith("pbkdf2_sha256$"):
        try:
            _, rounds, salt, digest = value.split("$", 3)
            current = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt.encode("utf-8"), int(rounds)).hex()
            return hmac.compare_digest(current, digest)
        except: return False
    legacy = hashlib.sha256((password or "").encode("utf-8")).hexdigest()
    return hmac.compare_digest(value, legacy)

def is_rate_limited(request, action: str, identity: str = "", max_attempts: int = 5, window_sec: int = 300, block_sec: int = 600):
    from db import get_conn, execute
    now = int(time.time())
    key = _auth_key(request, action, identity)
    conn = get_conn()
    cur = conn.cursor()
    execute(cur, "SELECT window_start, attempts, blocked_until FROM auth_rate_limits WHERE rate_key=?", (key,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, 0
    window_start, attempts, blocked_until = int(row[0]), int(row[1]), int(row[2])
    if blocked_until > now:
        conn.close()
        return True, blocked_until - now
    if now - window_start > window_sec:
        execute(cur, "DELETE FROM auth_rate_limits WHERE rate_key=?", (key,))
        conn.commit()
        conn.close()
        return False, 0
    if attempts >= max_attempts:
        execute(cur, "UPDATE auth_rate_limits SET blocked_until=? WHERE rate_key=?", (now + block_sec, key))
        conn.commit()
        conn.close()
        return True, block_sec
    conn.close()
    return False, 0

def record_auth_failure(request, action: str, identity: str = "", window_sec: int = 300):
    from db import get_conn, execute
    now = int(time.time())
    key = _auth_key(request, action, identity)
    conn = get_conn()
    cur = conn.cursor()
    execute(cur, "SELECT window_start, attempts FROM auth_rate_limits WHERE rate_key=?", (key,))
    row = cur.fetchone()
    if not row:
        execute(cur, "INSERT INTO auth_rate_limits(rate_key, window_start, attempts, blocked_until) VALUES(?,?,?,?)", (key, now, 1, 0))
    else:
        window_start, attempts = int(row[0]), int(row[1])
        if now - window_start > window_sec:
            execute(cur, "UPDATE auth_rate_limits SET window_start=?, attempts=?, blocked_until=0 WHERE rate_key=?", (now, 1, key))
        else:
            execute(cur, "UPDATE auth_rate_limits SET attempts=?, blocked_until=blocked_until WHERE rate_key=?", (attempts + 1, key))
    conn.commit()
    conn.close()

def record_auth_success(request, action: str, identity: str = ""):
    from db import get_conn, execute
    key = _auth_key(request, action, identity)
    conn = get_conn()
    cur = conn.cursor()
    execute(cur, "DELETE FROM auth_rate_limits WHERE rate_key=?", (key,))
    conn.commit()
    conn.close()

