from fastapi import APIRouter, Request, Form, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
from core import *

router = APIRouter()

@router.get("/healthz")
def healthz():
    return {"status": "ok", "ts": int(time.time())}


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt():
    content = "User-agent: *\nAllow: /\nDisallow: /admin\n"
    return content


@router.get("/readyz")
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


@router.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request})


@router.get("/terms", response_class=HTMLResponse)
def terms(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request})




# LANDING PAGE
@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    log_event("page_view", "landing", metadata={"path": "/"})
    auth_notice = request.query_params.get("auth") == "required"
    return templates.TemplateResponse("index.html", {"request": request, "auth_notice": auth_notice})


@router.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("signup.html", {"request": request})


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if is_admin_session(request):
        return RedirectResponse("/admin", status_code=303)
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/account", response_class=HTMLResponse)
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


@router.get("/pricing", response_class=HTMLResponse)
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


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request})


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str = ""):
    return templates.TemplateResponse("reset_password.html", {"request": request, "token": token})


@router.get("/resume", response_class=HTMLResponse)
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


@router.get("/resume/compare", response_class=HTMLResponse)
def compare_resumes(request: Request, current_id: int = None, previous_id: int = None):
    log_event("page_view", "resume_compare", metadata={"current": current_id, "previous": previous_id})
    user_email = (request.session.get("user_email") or "").strip().lower()
    if not user_email:
        return RedirectResponse(url="/login")

    if not current_id or not previous_id:
        return templates.TemplateResponse("error.html", {"request": request, "message": "Missing comparison IDs."}, status_code=400)

    try:
        if int(current_id) == int(previous_id):
            return templates.TemplateResponse("error.html", {"request": request, "message": "Cannot compare a report with itself."}, status_code=400)
    except ValueError:
        return templates.TemplateResponse("error.html", {"request": request, "message": "Invalid IDs provided."}, status_code=400)

    current_report = get_resume_report_by_id_for_user(current_id, user_email)
    previous_report = get_resume_report_by_id_for_user(previous_id, user_email)

    if not current_report or not previous_report:
        return templates.TemplateResponse("error.html", {"request": request, "message": "One or both reports not found or access denied."}, status_code=404)

    # Read scores gracefully
    curr_scores = current_report.get("scores", {}) or current_report.get("score", {})
    prev_scores = previous_report.get("scores", {}) or previous_report.get("score", {})

    deltas = {}
    for k in curr_scores.keys():
        if k in prev_scores:
            try:
                deltas[k] = round(float(curr_scores[k] or 0) - float(prev_scores[k] or 0), 1)
            except Exception:
                deltas[k] = 0.0

    warning = ""
    if current_report.get("target_role") != previous_report.get("target_role"):
        warning = "Roles differ ({} vs {}). Evaluation weights might not be comparable.".format(
            current_report.get("target_role") or "Generic", previous_report.get("target_role") or "Generic"
        )

    return templates.TemplateResponse(
        "resume_compare.html",
        {
            "request": request,
            "current": current_report,
            "previous": previous_report,
            "curr_scores": curr_scores,
            "prev_scores": prev_scores,
            "deltas": deltas,
            "warning": warning,
            "all_zero": all(d == 0.0 for d in deltas.values()) if deltas else False,
            "user_plan": current_user_plan(request),
        }
    )


# UPLOAD ROUTE
@router.get("/interview", response_class=HTMLResponse)
def interview(request: Request):
    log_event("page_view", "interview_page", metadata={"path": "/interview"})
    return templates.TemplateResponse("interview.html", interview_context_payload(request))


@router.get("/coding", response_class=HTMLResponse)
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


@router.get("/coding/problems", response_class=HTMLResponse)
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


@router.get("/book-call", response_class=HTMLResponse)
def book(request: Request):
    log_event("page_view", "book_call_page", metadata={"path": "/book-call"})
    prefill = {
        "name": request.query_params.get("name", ""),
        "email": request.query_params.get("email", ""),
        "topic": request.query_params.get("topic", ""),
        "outcome": request.query_params.get("outcome", ""),
    }
    return templates.TemplateResponse("book_call.html", {"request": request, "prefill": prefill})


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


@router.get("/admin-login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    log_event("admin_login_page_view", "admin")
    return templates.TemplateResponse("admin_login.html", {"request": request})

@router.get("/admin", response_class=HTMLResponse)
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


@router.get("/admin/experiments", response_class=HTMLResponse)
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


@router.get("/admin/coding", response_class=HTMLResponse)
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


@router.get("/admin/safety", response_class=HTMLResponse)
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


@router.get("/admin/bookings", response_class=HTMLResponse)
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


@router.get("/admin/premium", response_class=HTMLResponse)
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


@router.post("/admin/premium/{premium_request_id}/approve")
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


@router.post("/admin/premium/{premium_request_id}/reject")
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


@router.post("/admin/booking/{booking_id}/assign-mentor")
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


@router.post("/admin/feedback")
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


@router.post("/admin/feedback/{feedback_id}/status")
def admin_feedback_status(feedback_id: int, request: Request, status: str = Form(...)):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    update_feedback_status(feedback_id, status)
    log_audit("admin", "feedback_status_updated", f"id={feedback_id},status={status}")
    return RedirectResponse("/admin/safety", status_code=303)


@router.post("/admin/experiments/save")
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


@router.post("/admin/abtest/save")
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


@router.post("/admin/safety/report")
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


@router.get("/admin/export")
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

@router.get("/admin-delete/{booking_id}")
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

@router.get("/admin-logout")
def admin_logout(request: Request):
    request.session.pop("admin", None)
    request.session.pop("admin_user", None)
    request.session.pop("user_plan", None)
    log_audit("admin", "admin_logout", "Session closed")
    return RedirectResponse("/admin-login", status_code=303)


import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

