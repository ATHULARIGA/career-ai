from fastapi import APIRouter, Request, Form, UploadFile, File, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
import time
from typing import Any, Dict
from urllib.parse import urlencode

# Modular imports
from core import templates, logger, DEFAULT_PROBLEMS
from db import (
    get_conn,
    execute,
    is_admin_session,
    current_user_plan,
    get_user_memory,
    is_premium_user
)
from features.shared.analytics import log_event, log_audit, admin_context_payload, upsert_experiment, upsert_ab_test
from features.shared.analytics import add_feedback, update_feedback_status, add_safety_event, export_all_csv, export_all_json
from features.coding.platform import (
    SUPPORTED_LANGUAGES,
    get_problem,
    get_all_problems,
    get_company_problems,
    company_sets,
    get_judge_job,
    coding_followup_questions,
    review_code_heuristic,
    editorial_bundle,
    coding_context_payload,
    plagiarism_alerts
)
from features.resume import (
    get_latest_resume_report_for_user,
    get_resume_report_by_id_for_user,
    resume_quota_state
)
from features.interview import interview_context_payload
from db.booking import get_bookings, assign_mentor_email
from features.shared.email import send_mail
from features.interview import build_pre_session_brief
from features.shared import call_ai_with_fallback, parse_json_object
from features.roadmap.generator import generate_mindmap
import json



# Local helpers moved from core.py
def user_progress_summary(email: str, conn=None) -> dict:
    return {
        "resume_runs_7d": 0, "resume_avg_7d": 0.0,
        "coding_submissions_7d": 0, "coding_accept_rate_7d": 0.0,
        "active_days_7d": 0, "current_streak_days": 0,
        "next_action": "Run your first resume review (8 min).",
    }

router = APIRouter()

@router.get("/healthz")
def healthz(): return {"status": "ok", "ts": int(time.time())}

@router.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt(): return "User-agent: *\nAllow: /\nDisallow: /admin\n"

@router.get("/readyz")
def readyz():
    try:
        conn = get_conn()
        cur = conn.cursor()
        execute(cur, "SELECT 1")
        cur.fetchone()
        conn.close()
        return {"status": "ready"}
    except Exception as e:
        return JSONResponse({"status": "not_ready", "error": str(e)}, status_code=503)

@router.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request): return templates.TemplateResponse(request=request, name="privacy.html", context={"request": request})

@router.get("/terms", response_class=HTMLResponse)
def terms(request: Request): return templates.TemplateResponse(request=request, name="terms.html", context={"request": request})

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    log_event("page_view", "landing", metadata={"path": "/"})
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request, "auth_notice": request.query_params.get("auth") == "required"})

@router.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    if request.session.get("user_id"): return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request=request, name="signup.html", context={"request": request})

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_admin_session(request): return RedirectResponse("/admin", status_code=303)
    if request.session.get("user_id"): return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request})

@router.get("/account", response_class=HTMLResponse)
def account_page(request: Request):
    if not request.session.get("user_id"): return RedirectResponse("/login", status_code=303)
    if is_admin_session(request): return RedirectResponse("/admin", status_code=303)
    user_email = (request.session.get("user_email") or "").strip().lower()
    conn = get_conn()
    try:
        memory = get_user_memory(user_email, conn=conn)
        progress = user_progress_summary(user_email, conn=conn)
    except Exception as account_error:
        logger.warning("account_snapshot_failed user=%s err=%s", user_email, str(account_error))
        memory = {"target_role": "", "target_company": "", "focus_area": ""}
        progress = user_progress_summary(user_email)
    finally: conn.close()
    return templates.TemplateResponse(request=request, name="account.html", context={"request": request, "user_plan": current_user_plan(request), "memory": memory, "progress": progress, "status": request.query_params.get("status", "")})

@router.get("/pricing", response_class=HTMLResponse)
def pricing_page(request: Request):
    if not request.session.get("user_id"): return RedirectResponse("/login", status_code=303)
    user_email = (request.session.get("user_email") or "").strip().lower()
    conn = get_conn()
    cur = conn.cursor()
    execute(cur, "SELECT id, upi_txn_ref, amount, screenshot_url, notes, status, rejection_reason, created_ts FROM premium_requests WHERE user_email=? ORDER BY created_ts DESC LIMIT 1", (user_email,))
    latest_request = cur.fetchone()
    conn.close()
    return templates.TemplateResponse(request=request, name="pricing.html", context={"request": request, "user_plan": current_user_plan(request), "latest_request": latest_request, "status": request.query_params.get("status", "")})

@router.get("/resume", response_class=HTMLResponse)
def resume_page(request: Request):
    user_email = (request.session.get("user_email") or "").strip().lower()
    return templates.TemplateResponse(request=request, name="upload.html", context={"request": request, "user_plan": current_user_plan(request), "resume_quota": resume_quota_state(request), "memory": get_user_memory(user_email)})

@router.get("/resume/compare", response_class=HTMLResponse)
def compare_resumes(request: Request, current_id: int = None, previous_id: int = None):
    user_email = (request.session.get("user_email") or "").strip().lower()
    if not user_email: return RedirectResponse(url="/login")
    current_report = get_resume_report_by_id_for_user(current_id, user_email)
    previous_report = get_resume_report_by_id_for_user(previous_id, user_email)
    if not current_report or not previous_report: return templates.TemplateResponse(request=request, name="error.html", context={"request": request, "message": "Reports not found."})
    return templates.TemplateResponse(request=request, name="resume_compare.html", context={"request": request, "current": current_report, "previous": previous_report, "user_plan": current_user_plan(request)})

@router.get("/interview", response_class=HTMLResponse)
def interview_page(request: Request, db_conn = Depends(get_conn)):
    payload = interview_context_payload(request)
    session_id_val = request.session.get("interview_id")
    if session_id_val:
        import json
        cur = db_conn.cursor()
        execute(cur, "SELECT qa_history_json FROM interview_sessions WHERE session_id=?", (session_id_val,))
        row = cur.fetchone()
        if row: payload["qa_history"] = json.loads(row[0] or "[]")
    return templates.TemplateResponse(request=request, name="interview.html", context=payload)

@router.get("/api/interview-progress", response_class=JSONResponse)
def interview_progress_api(request: Request):
    user_email = (request.session.get("user_email") or "").strip().lower()
    if not user_email:
        return JSONResponse(content=[])
    conn = get_conn()
    cur = conn.cursor()
    execute(
        cur,
        """
        SELECT created_at, overall_score
        FROM interview_sessions
        WHERE user_email=?
        ORDER BY created_at ASC
        LIMIT 50
        """,
        (user_email,),
    )
    rows = cur.fetchall()
    conn.close()
    points = []
    for ts, score in rows:
        try:
            ts_int = int(ts or 0)
            score_val = float(score or 0)
            if ts_int <= 0:
                continue
            points.append({"date": time.strftime("%b %d", time.localtime(ts_int)), "score": round(score_val, 1)})
        except Exception:
            continue
    return JSONResponse(content=points)

@router.get("/admin", response_class=HTMLResponse)

@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    conn = get_conn()
    cur = conn.cursor()
    execute(
        cur,
        """
        SELECT full_name, email, created_ts
        FROM users
        ORDER BY created_ts DESC
        LIMIT 25
        """,
    )
    recent_users = cur.fetchall()
    conn.close()
    return templates.TemplateResponse(
        request=request,
        name="admin_overview.html",
        context={
            **admin_context_payload(request),
            "active_admin_page": "overview",
            "recent_users": recent_users,
        },
    )

@router.get("/admin/experiments", response_class=HTMLResponse)
def admin_experiments_page(request: Request):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="admin_experiments.html",
        context={**admin_context_payload(request), "active_admin_page": "experiments"},
    )

@router.post("/admin/experiments/save", response_class=RedirectResponse)
def admin_experiments_save(
    request: Request,
    feature: str = Form(...),
    prompt_version: str = Form(...),
    model_name: str = Form(...),
    enabled: str = Form(""),
):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login", status_code=303)
    upsert_experiment(
        feature=(feature or "").strip(),
        prompt_version=(prompt_version or "").strip(),
        model_name=(model_name or "").strip(),
        enabled=bool((enabled or "").strip()),
    )
    log_audit("admin", "experiment_saved", f"feature={feature},model={model_name},enabled={1 if enabled else 0}")
    return RedirectResponse("/admin/experiments", status_code=303)

@router.get("/admin/coding", response_class=HTMLResponse)
def admin_coding_page(request: Request):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="admin_coding.html",
        context={
            **admin_context_payload(request),
            "active_admin_page": "coding",
            "import_status": request.query_params.get("import", ""),
        },
    )

@router.get("/admin/safety", response_class=HTMLResponse)
def admin_safety_page(request: Request):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="admin_safety.html",
        context={**admin_context_payload(request), "active_admin_page": "safety"},
    )

@router.get("/admin/bookings", response_class=HTMLResponse)
def admin_bookings_page(request: Request):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="admin_bookings.html",
        context={**admin_context_payload(request), "active_admin_page": "bookings"},
    )

@router.get("/admin/premium", response_class=HTMLResponse)
def admin_premium_page(request: Request):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login", status_code=303)
    conn = get_conn()
    cur = conn.cursor()
    execute(
        cur,
        """
        SELECT id, user_email, upi_txn_ref, amount, screenshot_url, notes, status, rejection_reason, created_ts
        FROM premium_requests
        ORDER BY created_ts DESC
        """,
    )
    premium_requests = cur.fetchall()
    conn.close()
    return templates.TemplateResponse(
        request=request,
        name="admin_premium.html",
        context={
            **admin_context_payload(request),
            "active_admin_page": "premium",
            "premium_requests": premium_requests,
            "status": request.query_params.get("status", ""),
        },
    )

@router.get("/admin/export")
def admin_export(request: Request, format: str = "json"):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login", status_code=303)
    data = get_bookings()
    fmt = (format or "json").strip().lower()
    if fmt == "csv":
        return PlainTextResponse(
            content=export_all_csv(data),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=admin_export.csv"},
        )
    return PlainTextResponse(
        content=export_all_json(data),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=admin_export.json"},
    )

@router.get("/admin-logout")
def admin_logout(request: Request):
    request.session.pop("admin", None)
    request.session.pop("admin_user", None)
    request.session.pop("user_role", None)
    request.session.pop("user_plan", None)
    request.session.clear()
    return RedirectResponse("/admin-login", status_code=303)

@router.post("/admin/feedback")
def admin_add_feedback(
    request: Request,
    source: str = Form(...),
    severity: str = Form(...),
    message: str = Form(...),
):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login", status_code=303)
    add_feedback(source=(source or "").strip(), severity=(severity or "").strip(), message=(message or "").strip())
    return RedirectResponse("/admin/safety", status_code=303)

@router.post("/admin/feedback/{feedback_id}/status")
def admin_feedback_status(request: Request, feedback_id: int, status: str = Form(...)):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login", status_code=303)
    update_feedback_status(int(feedback_id), (status or "open").strip())
    return RedirectResponse("/admin/safety", status_code=303)

@router.post("/admin/safety/report")
def admin_safety_report(
    request: Request,
    level: str = Form(...),
    event_type: str = Form(...),
    payload: str = Form(""),
):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login", status_code=303)
    add_safety_event(level=(level or "").strip(), event_type=(event_type or "").strip(), payload=(payload or "").strip())
    return RedirectResponse("/admin/safety", status_code=303)

@router.post("/admin/booking/{booking_id}/assign-mentor")
def admin_assign_mentor(request: Request, booking_id: int, mentor_email: str = Form(...)):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login", status_code=303)
    mentor_email = (mentor_email or "").strip().lower()
    if "@" not in mentor_email:
        return RedirectResponse("/admin/bookings?mail=failed&reason=invalid_email", status_code=303)
    assign_mentor_email(int(booking_id), mentor_email)
    log_audit("admin", "mentor_assigned", f"booking_id={booking_id},mentor_email={mentor_email}")
    return RedirectResponse("/admin/bookings?mail=sent", status_code=303)

@router.get("/admin-delete/{booking_id}")
def admin_delete_booking(request: Request, booking_id: int):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login", status_code=303)
    conn = get_conn()
    cur = conn.cursor()
    execute(cur, "DELETE FROM bookings WHERE id=?", (int(booking_id),))
    conn.commit()
    conn.close()
    return RedirectResponse("/admin/bookings", status_code=303)

@router.post("/admin/premium/{request_id}/approve")
def admin_approve_premium(request: Request, request_id: int):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login", status_code=303)
    conn = get_conn()
    cur = conn.cursor()
    execute(cur, "SELECT user_email FROM premium_requests WHERE id=?", (int(request_id),))
    row = cur.fetchone()
    if not row:
        conn.close()
        return RedirectResponse("/admin/premium?status=not-found", status_code=303)
    user_email = (row[0] or "").strip().lower()
    execute(cur, "UPDATE premium_requests SET status='approved', rejection_reason='' WHERE id=?", (int(request_id),))
    execute(cur, "UPDATE users SET plan='premium' WHERE email=?", (user_email,))
    conn.commit()
    conn.close()
    log_audit("admin", "premium_request_approved", f"request_id={request_id},email={user_email}")
    return RedirectResponse("/admin/premium?status=approved", status_code=303)

@router.post("/admin/premium/{request_id}/reject")
def admin_reject_premium(request: Request, request_id: int, rejection_reason: str = Form("")):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login", status_code=303)
    conn = get_conn()
    cur = conn.cursor()
    execute(cur, "SELECT user_email FROM premium_requests WHERE id=?", (int(request_id),))
    row = cur.fetchone()
    if not row:
        conn.close()
        return RedirectResponse("/admin/premium?status=not-found", status_code=303)
    user_email = (row[0] or "").strip().lower()
    execute(
        cur,
        "UPDATE premium_requests SET status='rejected', rejection_reason=? WHERE id=?",
        ((rejection_reason or "").strip()[:200], int(request_id)),
    )
    execute(cur, "UPDATE users SET plan='free' WHERE email=?", (user_email,))
    conn.commit()
    conn.close()
    log_audit("admin", "premium_request_rejected", f"request_id={request_id},email={user_email}")
    return RedirectResponse("/admin/premium?status=rejected", status_code=303)

@router.get("/career-map", response_class=HTMLResponse)
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

@router.post("/mindmap")
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
        return JSONResponse(content=data)
    except Exception as e:
        logger.error(f"Error generating mindmap: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

@router.post("/skill-info")
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
    prompt = f"Provide a brief 2-sentence description of the skill '{skill}' and 3 learning resource links (Label and URL) in JSON format: {{'description': '...', 'resources': [{{'label': '...', 'url': '...'}}]}}"
    try:
        raw_res = call_ai_with_fallback("", prompt, max_tokens=1000)
        parsed = raw_res if isinstance(raw_res, dict) else parse_json_object(raw_res)
        description = str(parsed.get("description", "No description available.")).strip()
        resources = parsed.get("resources", [])
        if not isinstance(resources, list): resources = []
        safe_resources = []
        for item in resources[:3]:
            if not isinstance(item, dict): continue
            label = str(item.get("label", "Resource")).strip() or "Resource"
            url = str(item.get("url", "")).strip()
            if url.startswith("http://") or url.startswith("https://"):
                safe_resources.append({"label": label, "url": url})
        return JSONResponse(content={"description": description, "resources": safe_resources})
    except Exception as e:
        logger.error(f"Skill info error: {e}")
        return JSONResponse(content={"description": "Resource data temporarily limited.", "resources": []})
