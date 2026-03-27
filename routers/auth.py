from fastapi import APIRouter, Request, Form, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
import logging
import traceback
import time
import secrets

# Modular imports
from core import templates, logger
from db import (
    get_conn,
    execute,
    hash_password,
    verify_password,
    save_user_memory,
    is_premium_user,
    is_admin_session,
    get_admin_settings
)
from features.shared.analytics import log_audit, log_event
from features.shared import validate_password_strength

# Local auth helpers (originally in core.py or shared)
_rate_limits = {} 
def is_rate_limited(request: Request, action: str, identity: str, max_attempts=5, window_sec=60, block_sec=300):
    now = time.time()
    key = f"{action}:{identity}"
    attempts = _rate_limits.get(key, [])
    attempts = [t for t in attempts if now - t < window_sec]
    if len(attempts) >= max_attempts:
        return True, block_sec
    attempts.append(now)
    _rate_limits[key] = attempts
    return False, 0

def record_auth_success(request: Request, action: str, identity: str):
    key = f"{action}:{identity}"
    _rate_limits.pop(key, None)

def record_auth_failure(request: Request, action: str, identity: str):
    pass # Already tracked in is_rate_limited

def send_mail(email, subject, body, link=None):
    logger.info(f"SIMULATED EMAIL to {email}: {subject}\n{body}")
    return True

router = APIRouter()

@router.post("/signup", response_class=HTMLResponse)
def signup(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    website: str = Form(""),
):
    if (website or "").strip():
        return templates.TemplateResponse(request=request, name="signup.html", context={"request": request, "error": "Request blocked."})
    full_name = full_name.strip()
    email = email.strip().lower()

    if len(full_name) < 2:
        return templates.TemplateResponse(request=request, name="signup.html", context={"request": request, "error": "Enter a valid name."})
    if "@" not in email or "." not in email:
        return templates.TemplateResponse(request=request, name="signup.html", context={"request": request, "error": "Enter a valid email."})
    pw_error = validate_password_strength(password)
    if pw_error:
        return templates.TemplateResponse(request=request, name="signup.html", context={"request": request, "error": pw_error})
    if password != confirm_password:
        return templates.TemplateResponse(request=request, name="signup.html", context={"request": request, "error": "Passwords do not match."})

    conn = get_conn()
    cur = conn.cursor()
    try:
        execute(cur, "SELECT id FROM users WHERE email=?", (email,))
        if cur.fetchone():
            conn.close()
            return templates.TemplateResponse(
                request=request,
                name="signup.html",
                context={"request": request, "error": "An account with this email already exists."},
            )
        execute(cur,
            "INSERT INTO users(full_name,email,password_hash,role,password_updated_ts,created_ts) VALUES(?,?,?,?,?,?)",
            (full_name, email, hash_password(password), "user", int(time.time()), int(time.time())),
        )
        conn.commit()
        execute(cur, "SELECT id FROM users WHERE email=?", (email,))
        row = cur.fetchone()
        user_id = int((row or [0])[0] or 0)
    except Exception as e:
        logger.error("Signup error: %s", traceback.format_exc())
        conn.close()
        return templates.TemplateResponse(request=request, name="signup.html", context={"request": request, "error": "Signup failed."})
    conn.close()

    request.session["user_id"] = int(user_id)
    request.session["user_name"] = full_name
    request.session["user_email"] = email
    request.session["user_role"] = "user"
    request.session["user_plan"] = "free"
    return RedirectResponse("/", status_code=303)

@router.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    website: str = Form(""),
):
    if (website or "").strip():
        return templates.TemplateResponse(request=request, name="login.html", context={"request": request, "error": "Request blocked."})
    identity = email.strip()
    email = identity.lower()
    blocked, retry = is_rate_limited(request, "login", identity=email)
    if blocked:
        return templates.TemplateResponse(request=request, name="login.html", context={"request": request, "error": f"Too many attempts. Try again in {retry}s."})

    admin_username, admin_password, admin_email = get_admin_settings()
    is_admin_identity = (
        (admin_username and identity.lower() == admin_username.lower())
        or (admin_email and email == admin_email.lower())
    )
    if admin_password and is_admin_identity and password == admin_password:
        request.session.pop("admin", None)
        request.session["user_id"] = -1
        request.session["user_name"] = "Admin"
        request.session["user_email"] = admin_email or admin_username
        request.session["user_role"] = "admin"
        request.session["user_plan"] = "premium"
        record_auth_success(request, "login", identity=email)
        log_audit("admin", "admin_site_login", "Admin logged into site")
        return RedirectResponse("/", status_code=303)

    conn = get_conn()
    cur = conn.cursor()
    execute(cur, "SELECT id, full_name, email, password_hash, role, plan FROM users WHERE email=?", (email,))
    row = cur.fetchone()
    if not row or not verify_password(row[3], password):
        conn.close()
        record_auth_failure(request, "login", identity=email)
        return templates.TemplateResponse(request=request, name="login.html", context={"request": request, "error": "Invalid email or password."})
    
    # Hash upgrade if legacy
    if not str(row[3]).startswith("pbkdf2_sha256$"):
        execute(cur, "UPDATE users SET password_hash=?, password_updated_ts=? WHERE id=?", (hash_password(password), int(time.time()), int(row[0])))
        conn.commit()
    conn.close()
    record_auth_success(request, "login", identity=email)

    request.session["user_id"] = int(row[0])
    request.session["user_name"] = row[1]
    request.session["user_email"] = row[2]
    request.session["user_role"] = row[4] or "user"
    request.session["user_plan"] = (row[5] or "free")
    return RedirectResponse("/", status_code=303)

@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)

@router.post("/account/memory")
def save_account_memory_route(request: Request, target_role: str = Form(""), target_company: str = Form(""), focus_area: str = Form("")):
    if not request.session.get("user_id") or is_admin_session(request):
        return RedirectResponse("/login", status_code=303)
    user_email = (request.session.get("user_email") or "").strip().lower()
    save_user_memory(user_email, target_role, target_company, focus_area)
    return RedirectResponse("/account?status=memory-saved", status_code=303)

@router.post("/premium/request")
def create_premium_request(request: Request, upi_txn_ref: str = Form(...), amount: str = Form(""), screenshot_url: str = Form(""), notes: str = Form("")):
    if not request.session.get("user_id") or is_admin_session(request):
        return RedirectResponse("/login", status_code=303)
    user_id = int(request.session.get("user_id") or 0)
    user_email = (request.session.get("user_email") or "").strip().lower()
    if is_premium_user(request):
        return RedirectResponse("/pricing?status=already-premium", status_code=303)

    upi_txn_ref = (upi_txn_ref or "").strip()
    if len(upi_txn_ref) < 5:
        return RedirectResponse("/pricing?status=invalid-ref", status_code=303)

    conn = get_conn()
    cur = conn.cursor()
    execute(cur, "SELECT id FROM premium_requests WHERE user_email=? AND status='pending'", (user_email,))
    if cur.fetchone():
        conn.close()
        return RedirectResponse("/pricing?status=already-pending", status_code=303)

    execute(cur, "INSERT INTO premium_requests(user_id,user_email,upi_txn_ref,amount,screenshot_url,notes,status,created_ts) VALUES(?,?,?,?,?,?,?,?)",
            (user_id, user_email, upi_txn_ref[:120], amount[:40], screenshot_url[:400], notes[:1000], "pending", int(time.time())))
    conn.commit()
    conn.close()
    log_audit(user_email, "premium_request_submitted", f"txn={upi_txn_ref[:40]}")
    return RedirectResponse("/pricing?status=submitted", status_code=303)

@router.post("/account/delete")
def delete_account(request: Request):
    user_email = (request.session.get("user_email") or "").strip().lower()
    if not user_email or is_admin_session(request):
        return RedirectResponse("/", status_code=303)
    conn = get_conn()
    cur = conn.cursor()
    execute(cur, "DELETE FROM users WHERE email=?", (user_email,))
    execute(cur, "DELETE FROM resume_reports WHERE user_email=?", (user_email,))
    execute(cur, "DELETE FROM coding_submissions WHERE user_email=?", (user_email,))
    execute(cur, "DELETE FROM premium_requests WHERE user_email=?", (user_email,))
    execute(cur, "DELETE FROM user_memory WHERE user_email=?", (user_email,))
    conn.commit()
    conn.close()
    request.session.clear()
    return RedirectResponse("/", status_code=303)

@router.post("/forgot-password", response_class=HTMLResponse)
def forgot_password(request: Request, email: str = Form(...), website: str = Form("")):
    if (website or "").strip():
        return templates.TemplateResponse(request=request, name="forgot_password.html", context={"request": request, "error": "Request blocked."})
    email = (email or "").strip().lower()
    blocked, retry = is_rate_limited(request, "forgot_password", identity=email, max_attempts=4, window_sec=300, block_sec=900)
    if blocked:
        return templates.TemplateResponse(request=request, name="forgot_password.html", context={"request": request, "error": f"Too many requests. Try in {retry}s."})
    
    conn = get_conn()
    cur = conn.cursor()
    execute(cur, "SELECT id FROM users WHERE email=?", (email,))
    row = cur.fetchone()
    if row:
        token = secrets.token_urlsafe(28)
        expiry = int(time.time()) + 1800
        execute(cur, "UPDATE users SET reset_token=?, reset_token_expiry=? WHERE id=?", (token, expiry, int(row[0])))
        conn.commit()
        reset_link = f"{str(request.base_url).rstrip('/')}/reset-password?token={token}"
        send_mail(email, "Password Reset", f"Link: {reset_link}")
    conn.close()
    return templates.TemplateResponse(request=request, name="forgot_password.html", context={"request": request, "message": "Reset link sent if email exists."})

@router.post("/reset-password", response_class=HTMLResponse)
def reset_password(request: Request, token: str = Form(""), password: str = Form(...), confirm_password: str = Form(...), website: str = Form("")):
    if (website or "").strip():
        return templates.TemplateResponse(request=request, name="reset_password.html", context={"request": request, "error": "Blocked.", "token": token})
    token = (token or "").strip()
    pw_error = validate_password_strength(password)
    if pw_error:
        return templates.TemplateResponse(request=request, name="reset_password.html", context={"request": request, "error": pw_error, "token": token})
    if password != confirm_password:
        return templates.TemplateResponse(request=request, name="reset_password.html", context={"request": request, "error": "Passwords mismatch.", "token": token})

    conn = get_conn()
    cur = conn.cursor()
    execute(cur, "SELECT id, email, reset_token_expiry FROM users WHERE reset_token=?", (token,))
    row = cur.fetchone()
    if not row or int(row[2] or 0) < int(time.time()):
        conn.close()
        return templates.TemplateResponse(request=request, name="reset_password.html", context={"request": request, "error": "Invalid token.", "token": token})
    execute(cur, "UPDATE users SET password_hash=?, password_updated_ts=?, reset_token=NULL, reset_token_expiry=0 WHERE id=?", (hash_password(password), int(time.time()), int(row[0])))
    conn.commit()
    conn.close()
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request, "message": "Password reset successful."})
