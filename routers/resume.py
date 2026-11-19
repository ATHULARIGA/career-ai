from typing import Optional
from fastapi import APIRouter, Request, Form, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse, Response
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
    source_type: str = Form("file"),
    saved_resume_id: int = Form(0),
    latex_code: str = Form(""),
    save_resume: str = Form(""),
    resume_title: str = Form(""),
    file: Optional[UploadFile] = File(None),
):
    start = time.time()
    quota = resume_quota_state(request)
    user_email = (request.session.get("user_email") or "").strip().lower()

    if not quota.get("is_premium") and int(quota.get("remaining", 0)) <= 0:
        saved_res = get_user_saved_resumes(user_email) if user_email else []
        if not saved_res:
            saved_res = [{
                "id": 1,
                "title": "Athul Ariga - Data Engineer & Python Developer (LaTeX)",
                "resume_type": "latex",
                "raw_content": DEFAULT_ATHUL_RESUME,
                "target_role": "Data Engineer & Python Developer",
                "created_ts": int(time.time()),
                "is_sample": True
            }]
        return templates.TemplateResponse(
            request=request,
            name="upload.html",
            context={
                "request": request,
                "user_plan": quota.get("plan", "free"),
                "resume_quota": quota,
                "quota_error": "Free plan daily limit reached. Upgrade to Premium for unlimited resume reviews.",
                "memory": get_user_memory(user_email),
                "saved_resumes": saved_res,
            },
        )
    try:
        raw_latex = ""
        text = ""

        # 1. Source: Selected Saved Resume
        if source_type == "saved" or (saved_resume_id > 0 and not (file and file.filename) and not latex_code.strip()):
            saved = get_saved_resume_by_id(saved_resume_id, user_email) if user_email else None
            if not saved:
                saved = get_saved_resume_by_id(saved_resume_id, "athulariga12@gmail.com")
            if not saved and (saved_resume_id == 1 or not user_email):
                saved = {
                    "id": 1,
                    "title": "Athul Ariga - Data Engineer & Python Developer (LaTeX)",
                    "resume_type": "latex",
                    "raw_content": DEFAULT_ATHUL_RESUME,
                    "target_role": "Data Engineer & Python Developer",
                }
            if not saved:
                raise ValueError("Selected saved resume was not found. Please paste LaTeX code or upload your file.")
            if saved.get("resume_type") == "latex":
                raw_latex = saved.get("raw_content", "")
                text = extract_text_from_latex(raw_latex)
            else:
                text = saved.get("raw_content", "")
            if not target_role.strip() and saved.get("target_role"):
                target_role = saved.get("target_role")

        # 2. Source: Pasted LaTeX Code
        elif source_type == "latex" or (latex_code.strip() and not (file and file.filename)):
            raw_latex = latex_code.strip()
            if not raw_latex:
                raise ValueError("Pasted LaTeX code cannot be empty.")
            text = extract_text_from_latex(raw_latex)
            if len(text.strip()) < 30:
                raise ValueError("Could not extract enough readable text from the pasted LaTeX code.")
            if save_resume in ("1", "on", "true") and user_email:
                t = resume_title.strip() or target_role.strip() or "LaTeX Resume"
                save_user_resume(user_email, t, "latex", raw_latex, target_role)

        # 3. Source: Uploaded File (PDF or .tex)
        else:
            if not file or not file.filename:
                raise ValueError("Please select a file to upload, paste your LaTeX code, or select a saved resume.")
            filename = (file.filename or "").lower()
            content = await file.read()
            if len(content or b"") > MAX_UPLOAD_BYTES:
                raise ValueError(f"File too large. Max allowed size is {MAX_UPLOAD_BYTES // 1_000_000}MB.")

            if filename.endswith(".tex"):
                raw_latex = content.decode("utf-8", errors="ignore")
                text = extract_text_from_latex(raw_latex)
                if save_resume in ("1", "on", "true") and user_email:
                    t = resume_title.strip() or file.filename or target_role.strip() or "LaTeX Resume"
                    save_user_resume(user_email, t, "latex", raw_latex, target_role)
            elif filename.endswith(".pdf"):
                content_type = (file.content_type or "").lower()
                if content_type and content_type not in ("application/pdf", "application/x-pdf", "binary/octet-stream"):
                    raise ValueError("Invalid file type. Please upload a PDF.")
                text = extract_text(file.filename, content)
                if save_resume in ("1", "on", "true") and user_email:
                    t = resume_title.strip() or file.filename or target_role.strip() or "PDF Resume"
                    save_user_resume(user_email, t, "pdf_text", text, target_role)
            else:
                raise ValueError("Only PDF (.pdf) and LaTeX (.tex) resumes are supported.")

        if not text.strip():
            raise ValueError("Could not extract readable text from your resume. Please check the content.")
        
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
        if raw_latex:
            report["latex_code"] = raw_latex
            report["original_latex"] = raw_latex
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
async def fix_resume_endpoint(request: Request, report_id: int, custom_jd: str = Form("")):
    user_email = (request.session.get("user_email") or "").strip().lower()
    if not user_email:
        return RedirectResponse("/login")
        
    report = get_resume_report_by_id_for_user(report_id, user_email)
    if not report:
        raise ValueError("Report not found or access denied.")
        
    resume_text = report.get("resume_text", "")
    if not resume_text.strip():
        report["fixed_resume_error"] = "Resume text unavailable for this historical report (pre-update). Please run a 'New Review' or re-upload your PDF below to use this feature."
        update_resume_report_json(report_id, user_email, report)
        return RedirectResponse(f"/resume/{report_id}/fix", status_code=303)

    if custom_jd.strip():
        report["jd_text"] = custom_jd.strip()
        
    from scoring import generate_tailored_latex_resume, generate_resume_rewrite
    jd_text = report.get("jd_text", "")
    if not report.get("original_latex") and report.get("latex_code"):
        report["original_latex"] = report.get("latex_code")
    tailored_result = generate_tailored_latex_resume(resume_text, report, jd_text)
    fixed_md = generate_resume_rewrite(resume_text, report)
    
    report["latex_code"] = tailored_result.get("latex_code", "")
    report["diff_changes"] = tailored_result.get("diff_changes", [])
    report["changes_summary"] = tailored_result.get("changes_summary", "")
    report["fixed_resume_md"] = fixed_md
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

        from scoring import generate_tailored_latex_resume, generate_resume_rewrite
        jd_text = report.get("jd_text", "")
        tailored_result = generate_tailored_latex_resume(text, report, jd_text)
        fixed_md = generate_resume_rewrite(text, report)

        report["latex_code"] = tailored_result.get("latex_code", "")
        report["diff_changes"] = tailored_result.get("diff_changes", [])
        report["changes_summary"] = tailored_result.get("changes_summary", "")
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
    latex_code = report.get("latex_code", "")
    diff_changes = report.get("diff_changes", [])
    changes_summary = report.get("changes_summary", "")
    target_role = report.get("target_role", "")
    jd_text = report.get("jd_text", "")
    error = report.get("fixed_resume_error", "")

    # Automatically generate tailored resume if missing or if only legacy 1-change fallback exists
    if (not diff_changes or len(diff_changes) <= 1) and report.get("resume_text"):
        try:
            from scoring import generate_tailored_latex_resume, generate_resume_rewrite
            resume_text = report.get("resume_text", "")
            if not report.get("original_latex") and report.get("latex_code"):
                report["original_latex"] = report.get("latex_code")
            tailored_result = generate_tailored_latex_resume(resume_text, report, jd_text)
            fixed_md = generate_resume_rewrite(resume_text, report)

            report["latex_code"] = tailored_result.get("latex_code", "")
            report["diff_changes"] = tailored_result.get("diff_changes", [])
            report["changes_summary"] = tailored_result.get("changes_summary", "")
            report["fixed_resume_md"] = fixed_md
            update_resume_report_json(report_id, user_email, report)

            latex_code = report["latex_code"]
            diff_changes = report["diff_changes"]
            changes_summary = report["changes_summary"]
            fixed_md = report["fixed_resume_md"]
        except Exception as gen_err:
            logger.warning("Auto tailoring in view_fixed_resume failed: %s", gen_err)

    warning = ""
    if not fixed_md and not latex_code and not error:
        warning = "Resume optimization not generated yet. Click Generate Tailored LaTeX Resume to create your tailored ATS resume."
         
    return templates.TemplateResponse(request=request, name="resume_fix.html", context={
         "request": request,
         "report_id": report_id,
         "fixed_md": fixed_md,
         "latex_code": latex_code,
         "diff_changes": diff_changes,
         "changes_summary": changes_summary,
         "target_role": target_role,
         "jd_text": jd_text,
         "warning": warning,
         "error": error,
         "user_plan": current_user_plan(request)
    })

@router.post("/resume/{report_id}/save-latex")
async def save_latex_endpoint(request: Request, report_id: int):
    user_email = (request.session.get("user_email") or "").strip().lower()
    if not user_email:
        return JSONResponse({"status": "error", "message": "Not authenticated"}, status_code=401)
    report = get_resume_report_by_id_for_user(report_id, user_email)
    if not report:
        return JSONResponse({"status": "error", "message": "Report not found"}, status_code=404)
    form = await request.form()
    latex_code = str(form.get("latex_code", ""))
    if not latex_code.strip():
        return JSONResponse({"status": "error", "message": "LaTeX code cannot be empty"}, status_code=400)
    report["latex_code"] = latex_code
    update_resume_report_json(report_id, user_email, report)
    return JSONResponse({"status": "success", "message": "LaTeX changes saved successfully"})

@router.get("/resume/{report_id}/download-latex")
async def download_latex_endpoint(request: Request, report_id: int):
    user_email = (request.session.get("user_email") or "").strip().lower()
    if not user_email:
        return RedirectResponse("/login")
    report = get_resume_report_by_id_for_user(report_id, user_email)
    if not report or not report.get("latex_code"):
        return RedirectResponse(f"/resume/{report_id}/fix")
    latex_code = report.get("latex_code", "")
    target_role = (report.get("target_role") or "resume").lower().replace(" ", "_")
    filename = f"{target_role}_tailored.tex"
    return Response(
        content=latex_code,
        media_type="application/x-tex",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/resume/compare", response_class=HTMLResponse)
def compare_resumes(request: Request, current_id: Optional[int] = None, previous_id: Optional[int] = None):
    log_event("page_view", "resume_compare", metadata={"current": current_id, "previous": previous_id})
    user_email = (request.session.get("user_email") or "").strip().lower()
    if not user_email:
        return RedirectResponse(url="/login")

    if not current_id or not previous_id:
        return templates.TemplateResponse(request=request, name="error.html", context={"request": request, "message": "Missing comparison IDs."}, status_code=400)

    try:
        if int(current_id) == int(previous_id):
            return templates.TemplateResponse(request=request, name="error.html", context={"request": request, "message": "Cannot compare a report with itself."}, status_code=400)
    except ValueError:
        return templates.TemplateResponse(request=request, name="error.html", context={"request": request, "message": "Invalid IDs provided."}, status_code=400)

    current_report = get_resume_report_by_id_for_user(current_id, user_email)
    previous_report = get_resume_report_by_id_for_user(previous_id, user_email)

    if not current_report or not previous_report:
        return templates.TemplateResponse(request=request, name="error.html", context={"request": request, "message": "One or both reports not found or access denied."}, status_code=404)

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
    
    tier_a = current_report.get("company_tier", "General") or "General"
    tier_b = previous_report.get("company_tier", "General") or "General"
    if tier_a != tier_b:
        tier_warning = "Company Tiers differ ({} vs {}). Evaluation weights are calibrated to different bars.".format(tier_a, tier_b)
        warning = (warning + " " + tier_warning) if warning else tier_warning

    return templates.TemplateResponse(
        request=request,
        name="resume_compare.html",
        context={
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


@router.post("/resume/saved/{resume_id}/delete")
async def delete_saved_resume_endpoint(request: Request, resume_id: int):
    user_email = (request.session.get("user_email") or "").strip().lower()
    if not user_email:
        return RedirectResponse("/login")
    delete_user_saved_resume(resume_id, user_email)
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return JSONResponse({"status": "success", "message": "Saved resume deleted successfully."})
    return RedirectResponse("/resume", status_code=303)


@router.get("/resume/saved/{resume_id}")
async def get_saved_resume_endpoint(request: Request, resume_id: int):
    user_email = (request.session.get("user_email") or "").strip().lower()
    if not user_email:
        return JSONResponse({"status": "error", "message": "Not authenticated"}, status_code=401)
    saved = get_saved_resume_by_id(resume_id, user_email)
    if not saved:
        return JSONResponse({"status": "error", "message": "Saved resume not found"}, status_code=404)
    return JSONResponse({"status": "success", "resume": saved})


# INTERVIEW PAGE
