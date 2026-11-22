import hashlib
import hmac
import os
import secrets
import time
from urllib.parse import urlparse
from dotenv import load_dotenv
from fastapi import Request
import db.backend as db
from core.config import APP_ENV, CSRF_STRICT


def get_admin_settings() -> tuple[str, str, str]:
    # Reload .env so credential changes apply without requiring a server restart.
    load_dotenv(override=True)
    admin_username = (os.getenv("ADMIN_USERNAME") or "").strip()
    admin_password = os.getenv("ADMIN_PASSWORD") or ""
    admin_email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
    return admin_username, admin_password, admin_email


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


def get_client_ip(request: Request) -> str:
    """
    Extract the real client IP address, handling proxy headers from Vercel / Cloudflare / Nginx.
    """
    if not request:
        return "127.0.0.1"
    headers = getattr(request, "headers", None) or {}
    forwarded = headers.get("x-forwarded-for")
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[0]
    real_ip = headers.get("x-real-ip")
    if real_ip and real_ip.strip():
        return real_ip.strip()
    try:
        client = getattr(request, "client", None)
        if client and getattr(client, "host", None):
            return client.host
    except Exception:
        pass
    return "127.0.0.1"


def get_client_geo(request: Request) -> dict:
    """
    Extract geographic location headers populated automatically by Vercel edge routers.
    """
    if not request:
        return {"country": "Unknown", "region": "Unknown", "city": "Unknown"}
    headers = getattr(request, "headers", None) or {}
    country = (headers.get("x-vercel-ip-country") or "").strip() or "Unknown"
    region = (headers.get("x-vercel-ip-country-region") or "").strip() or "Unknown"
    city = (headers.get("x-vercel-ip-city") or "").strip() or "Unknown"
    if city and "%" in city:
        import urllib.parse
        city = urllib.parse.unquote(city)
    return {
        "country": country,
        "region": region,
        "city": city,
    }


def _auth_key(request: Request, action: str, identity: str = "") -> str:
    ip = get_client_ip(request)
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


def is_admin_session(request: Request) -> bool:
    if request.session.get("admin") is True:
        return True
    return request.session.get("user_role") == "admin"


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
    if cached in ("free", "pro", "premium", "enterprise"):
        return cached
    plan = user_plan_for_email(request.session.get("user_email", ""))
    request.session["user_plan"] = plan
    return plan


def is_premium_user(request: Request) -> bool:
    return current_user_plan(request) == "premium"
