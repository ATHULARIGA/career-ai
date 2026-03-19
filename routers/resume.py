from fastapi import APIRouter, Request, Form, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
from core import *
from scoring import clean_scraped_jd

router = APIRouter()

@router.post("/upload", response_class=HTMLResponse)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    job_description: str = Form(""),
    job_link: str = Form(""),
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
        
        # Determine job description: Scrape link if provided, otherwise fallback to manual entry
        final_jd = job_description
        if job_link.strip():
            # 1. Rate Limit Guard
            if is_rate_limited(request, "scrape_job_link", max_attempts=10, window_sec=3600):
                raise ValueError("Rate limit exceeded for URL scraping. Please paste the JD text directly.")
                
            scrape_res = scrape_job_link(job_link.strip())
            if isinstance(scrape_res, dict) and scrape_res.get("error"):
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
        )
        report["resume_text"] = text
        report["jd_text"] = final_jd

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
    from starlette.templating import Jinja2Templates
    templates = Jinja2Templates(directory="templates")
    
    user_email = (request.session.get("user_email") or "").strip().lower()
    if not user_email:
         return RedirectResponse("/?auth=required")
         
    report = get_resume_report_by_id_for_user(report_id, user_email)
    if not report:
         return templates.TemplateResponse("error.html", {"request": request, "message": "Report not found or access denied."}, status_code=404)
         
    cover_letter = report.get("cover_letter_text", "")
    warning = ""
    # Explicit JD fallback alerts
    if not cover_letter:
        warning = "Cover letter not generated yet. Click generate below to create one."
    elif not report.get("jd_text") or len(report.get("jd_text", "").strip()) < 100:
        warning = "Empty or generic Job Description provided. This cover letter is generalized."
         
    return templates.TemplateResponse("cover_letter.html", {
         "request": request,
         "cover_letter": cover_letter,
         "report_id": report_id,
         "warning": warning,
         "user_plan": current_user_plan(request)
    })

# INTERVIEW PAGE
