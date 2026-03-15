from fastapi import APIRouter, Request, Form, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
from core import *
import logging
import traceback

_log = logging.getLogger(__name__)

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
        # Check if email already exists first – gives a clear, user-friendly error
        db.execute(cur, "SELECT id FROM users WHERE email=?", (email,))
        if cur.fetchone():
            conn.close()
            return templates.TemplateResponse(
                "signup.html",
                {"request": request, "error": "An account with this email already exists. Try logging in or use a different email."},
            )
        db.execute(cur,
            "INSERT INTO users(full_name,email,password_hash,role,password_updated_ts,created_ts) VALUES(?,?,?,?,?,?)",
            (full_name, email, hash_password(password), "user", int(time.time()), int(time.time())),
        )
        conn.commit()
        db.execute(cur, "SELECT id FROM users WHERE email=?", (email,))
        row = cur.fetchone()
        user_id = int((row or [0])[0] or 0)
    except Exception as e:
        err_detail = traceback.format_exc()
        _log.error("Signup error: %s", err_detail)
        try:
            conn.close()
        except Exception:
            pass
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Signup failed. Please try again or contact support."})
    conn.close()

    request.session["user_id"] = int(user_id)
    request.session["user_name"] = full_name
    request.session["user_email"] = email
    request.session["user_role"] = "user"
    request.session["user_plan"] = "free"
    request.session.pop("admin", None)
    request.session.pop("admin_user", None)
    return RedirectResponse("/", status_code=303)


@router.post("/login", response_class=HTMLResponse)
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


@router.get("/logout")
def logout(request: Request):
    request.session.pop("user_id", None)
    request.session.pop("user_name", None)
    request.session.pop("user_email", None)
    request.session.pop("user_role", None)
    request.session.pop("user_plan", None)
    request.session.pop("admin", None)
    request.session.pop("admin_user", None)
    return RedirectResponse("/", status_code=303)


@router.post("/account/memory")
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


@router.post("/premium/request")
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


@router.post("/account/delete")
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


@router.post("/forgot-password", response_class=HTMLResponse)
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


@router.post("/reset-password", response_class=HTMLResponse)
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
