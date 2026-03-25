from fastapi import APIRouter, Request, Form, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
from core import *
from scoring import clean_scraped_jd

router = APIRouter()

@router.post("/upload", response_class=HTMLResponse)
async def upload(
    request: Request,
    job_description: str = Form(""),
    job_link: str = Form(""),
    target_role: str = Form(""),
    seniority: str = Form(""),
    region: str = Form("US"),
    company_tier: str = Form("General"),
    file: UploadFile = File(...),
):
    with open("/tmp/upload_debug.txt", "w") as f:
        f.write(f"company_tier: {company_tier}\n")
    start = time.time()
    quota = resume_quota_state(request)
    if not quota.get("is_premium") and int(quota.get("remaining", 0)) <= 0:
        user_email = (request.session.get("user_email") or "").strip().lower()
        return templates.TemplateResponse(
            request=request,
            name="upload.html",
            context={
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
        
        # Determine job description: Scrape link if provided, otherwise fallback to manual entry
        final_jd = job_description
        if job_link.strip():
            # 1. Rate Limit Guard
            scrape_res = {}
            is_blocked, wait_sec = is_rate_limited(request, "scrape_job_link", max_attempts=10, window_sec=3600)
            
            if is_blocked:
                if not final_jd.strip():
                    wait_str = f"{wait_sec // 60}m {wait_sec % 60}s" if wait_sec > 60 else f"{wait_sec}s"
                    raise ValueError(f"Rate limit exceeded for URL scraping. Please wait {wait_str}, or paste the JD text directly.")
            else:
                scrape_res = scrape_job_link(job_link.strip())
                if isinstance(scrape_res, dict) and scrape_res.get("error"):
                    if not final_jd.strip():
                        raise ValueError(scrape_res.get("error"))
                
            scraped_text = scrape_res.get("text", "") if isinstance(scrape_res, dict) else ""
            if not scraped_text.strip():
                if not final_jd.strip():
                    raise ValueError("Could not extract a readable job description from the provided URL. Please try pasting the text manually instead.")
            else:
                # 2. AI Cleanup for large text
                if len(scraped_text) > 3000:
                    scraped_text = clean_scraped_jd(scraped_text)
                final_jd = f"Scraped from {job_link}:\n\n{scraped_text}"

        consume_resume_quota(request)
        report = score_resume(
            text=text,
            job_description=final_jd,
            target_role=target_role,
            seniority=seniority,
            region=region,
            company_tier=company_tier,
        )
        report["resume_text"] = text
        report["jd_text"] = final_jd
        report["company_tier"] = company_tier

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
                if version_history:
                    report["id"] = max(v["id"] for v in version_history)
                    with open("/tmp/id_debug.txt", "w") as f:
                        f.write(f"Assigned ID: {report['id']}\nVersion History: {[v['id'] for v in version_history]}\n")
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
        import urllib.parse
        error_msg = urllib.parse.quote(str(e))
        return RedirectResponse(f"/resume?error={error_msg}", status_code=303)

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
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


@router.get("/resume/export")
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


@router.post("/resume/{report_id}/cover_letter", response_class=RedirectResponse)
async def generate_cover_letter_endpoint(request: Request, report_id: int):
    user_email = (request.session.get("user_email") or "").strip().lower()
    if not user_email:
        return RedirectResponse("/login")
        
    report = get_resume_report_by_id_for_user(report_id, user_email)
    if not report:
        raise ValueError("Report not found or access denied.")
        
    resume_text = report.get("resume_text", "")
    jd_text = report.get("jd_text", "")
    
    from scoring import generate_cover_letter
    cover_letter = generate_cover_letter(resume_text, jd_text, report)
    
    report["cover_letter_text"] = cover_letter
    update_resume_report_json(report_id, user_email, report)
    
    return RedirectResponse(f"/resume/{report_id}/cover_letter", status_code=303)

@router.get("/resume/{report_id}/cover_letter", response_class=HTMLResponse)
async def view_cover_letter_endpoint(request: Request, report_id: int):
    user_email = (request.session.get("user_email") or "").strip().lower()
    if not user_email:
         return RedirectResponse("/?auth=required")
         
    report = get_resume_report_by_id_for_user(report_id, user_email)
    if not report:
         return templates.TemplateResponse(request=request, name="error.html", context={"request": request, "message": "Report not found or access denied."}, status_code=404)
         
    cover_letter = report.get("cover_letter_text", "")
    warning = ""
    # Explicit JD fallback alerts
    if not cover_letter:
        warning = "Cover letter not generated yet. Click generate below to create one."
    elif not report.get("jd_text") or len(report.get("jd_text", "").strip()) < 100:
        warning = "Empty or generic Job Description provided. This cover letter is generalized."
         
    return templates.TemplateResponse(request=request, name="cover_letter.html", context={
         "request": request,
         "cover_letter": cover_letter,
         "report_id": report_id,
         "warning": warning,
         "user_plan": current_user_plan(request)
    })

@router.post("/resume/{report_id}/fix", response_class=RedirectResponse)
async def fix_resume_endpoint(request: Request, report_id: int):
    user_email = (request.session.get("user_email") or "").strip().lower()
    if not user_email:
        return RedirectResponse("/login")
        
    report = get_resume_report_by_id_for_user(report_id, user_email)
    if not report:
        raise ValueError("Report not found or access denied.")
        
    resume_text = report.get("resume_text", "")
    if not resume_text.strip():
        report["fixed_resume_error"] = "Resume text unavailable for this historical report (pre-update). Please run a 'New Review' to use this feature."
        update_resume_report_json(report_id, user_email, report)
        return RedirectResponse(f"/resume/{report_id}/fix", status_code=303)
        
    from scoring import generate_resume_rewrite
    fixed_md = generate_resume_rewrite(resume_text, report)
    
    report["fixed_resume_md"] = fixed_md
    # Clear any old error
    report.pop("fixed_resume_error", None)
    update_resume_report_json(report_id, user_email, report)
    
    return RedirectResponse(f"/resume/{report_id}/fix", status_code=303)

@router.post("/resume/{report_id}/fix-upload", response_class=RedirectResponse)
async def fix_resume_with_upload(request: Request, report_id: int, file: UploadFile = File(...)):
    """Allow users with legacy reports (missing resume_text) to re-supply their PDF and get a fix."""
    user_email = (request.session.get("user_email") or "").strip().lower()
    if not user_email:
        return RedirectResponse("/login", status_code=303)

    report = get_resume_report_by_id_for_user(report_id, user_email)
    if not report:
        return RedirectResponse("/resume", status_code=303)

    try:
        filename = (file.filename or "").lower()
        if not filename.endswith(".pdf"):
            report["fixed_resume_error"] = "Only PDF files are supported. Please re-upload your resume as a PDF."
            update_resume_report_json(report_id, user_email, report)
            return RedirectResponse(f"/resume/{report_id}/fix", status_code=303)

        content = await file.read()
        if not content:
            report["fixed_resume_error"] = "The uploaded file was empty. Please try again."
            update_resume_report_json(report_id, user_email, report)
            return RedirectResponse(f"/resume/{report_id}/fix", status_code=303)

        text = extract_text(file.filename, content)
        if not text.strip():
            report["fixed_resume_error"] = "Could not extract text from the uploaded PDF. Make sure it's not a scanned image."
            update_resume_report_json(report_id, user_email, report)
            return RedirectResponse(f"/resume/{report_id}/fix", status_code=303)

        # Save the extracted text so future calls work without re-uploading
        report["resume_text"] = text
        report.pop("fixed_resume_error", None)

        from scoring import generate_resume_rewrite
        fixed_md = generate_resume_rewrite(text, report)
        report["fixed_resume_md"] = fixed_md
        update_resume_report_json(report_id, user_email, report)

    except Exception as e:
        report["fixed_resume_error"] = f"Failed to process upload: {str(e)}"
        update_resume_report_json(report_id, user_email, report)

    return RedirectResponse(f"/resume/{report_id}/fix", status_code=303)

@router.get("/resume/{report_id}/fix", response_class=HTMLResponse)
async def view_fixed_resume_endpoint(request: Request, report_id: int):
    user_email = (request.session.get("user_email") or "").strip().lower()
    report = get_resume_report_by_id_for_user(report_id, user_email)
    if not report:
         return templates.TemplateResponse(request=request, name="error.html", context={"request": request, "message": "Report not found or access denied."}, status_code=404)
         
    fixed_md = report.get("fixed_resume_md", "")
    error = report.get("fixed_resume_error", "")
    warning = ""
    if not fixed_md and not error:
        warning = "Resume optimization not generated yet. Click Fix My Resume from the dashboard to create one."
         
    return templates.TemplateResponse(request=request, name="resume_fix.html", context={
         "request": request,
         "fixed_md": fixed_md,
         "report_id": report_id,
         "warning": warning,
         "error": error,
         "user_plan": current_user_plan(request)
    })

@router.get("/resume/{report_id}", response_class=HTMLResponse)
async def view_dashboard_by_id(request: Request, report_id: int):
    user_email = (request.session.get("user_email") or "").strip().lower()
    report = get_resume_report_by_id_for_user(report_id, user_email)
    if not report:
         return templates.TemplateResponse(request=request, name="error.html", context={"request": request, "message": "Report not found or access denied."}, status_code=404)
         
    report["id"] = report_id
         
    # Mimic dashboard variables setup from /upload
    version_history = []
    try:
        version_history = get_recent_resume_runs_for_user(user_email, limit=10)
    except Exception:
        version_history = request.session.get("resume_versions", [])

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "request": request,
        "report": report,
        "resume_versions": version_history,
        "user_plan": current_user_plan(request),
        "progress": safe_user_progress_summary(user_email),
        "analysis_inputs": {
            "target_role": report.get("target_role"),
            "seniority": report.get("seniority", ""),
            "region": report.get("region", "US"),
            "has_job_description": bool(report.get("jd_text", "").strip()),
        },
    })

@router.post("/resume/{report_id}/test_fit", response_class=RedirectResponse)
async def test_fit_endpoint(
    request: Request, 
    report_id: int, 
    target_role: str = Form(...), 
    company_tier: str = Form("General"), 
    jd_text: str = Form("")
):
    from fastapi import HTTPException
    user_email = (request.session.get("user_email") or "").strip().lower()
    if not user_email:
        return RedirectResponse("/login")
        
    report = get_resume_report_by_id_for_user(report_id, user_email)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found or access denied.")
        
    fits = report.get("alternative_fits", [])
    if len(fits) >= 5:
        report["multi_fit_error"] = "Maximum 5 role comparisons per report. Remove one to add another."
        update_resume_report_json(report_id, user_email, report)
        return RedirectResponse(f"/resume/{report_id}#tab-multirole", status_code=303)
        
    existing = [f.get("role", "").lower() for f in fits]
    if target_role.lower() in existing:
        report["multi_fit_error"] = "This role is already in your comparison list."
        update_resume_report_json(report_id, user_email, report)
        return RedirectResponse(f"/resume/{report_id}#tab-multirole", status_code=303)

    resume_text = report.get("resume_text", "")
    if not resume_text:
        report["multi_fit_error"] = "Resume text unavailable. Re-upload required."
        update_resume_report_json(report_id, user_email, report)
        return RedirectResponse(f"/resume/{report_id}#tab-multirole", status_code=303)

    from scoring import score_resume_lightweight
    result = score_resume_lightweight(resume_text, jd_text, target_role, company_tier)
    
    fit_entry = {
        "role": target_role,
        "tier": company_tier,
        "score": result.get("score", 0.0),
        "match": result.get("match_percent", 0),
        "summary": result.get("summary", ""),
        "timestamp": int(time.time())
    }
    fits.append(fit_entry)
    report["alternative_fits"] = fits
    report.pop("multi_fit_error", None)
    update_resume_report_json(report_id, user_email, report)
    
    return RedirectResponse(f"/resume/{report_id}", status_code=303)

@router.get("/resume/{report_id}/test_fit/remove/{index}", response_class=RedirectResponse)
async def remove_fit_endpoint(request: Request, report_id: int, index: int):
    user_email = (request.session.get("user_email") or "").strip().lower()
    if not user_email:
        return RedirectResponse("/login")
        
    from fastapi import HTTPException
    report = get_resume_report_by_id_for_user(report_id, user_email)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found or access denied.")
        
    fits = report.get("alternative_fits", [])
    if 0 <= index < len(fits):
        fits.pop(index)
        report["alternative_fits"] = fits
        update_resume_report_json(report_id, user_email, report)
        
    return RedirectResponse(f"/resume/{report_id}", status_code=303)

# INTERVIEW PAGE
