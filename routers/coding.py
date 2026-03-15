from fastapi import APIRouter, Request, Form, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
from core import *

router = APIRouter()

@router.post("/coding/run", response_class=HTMLResponse)
def coding_run(
    request: Request,
    problem_id: str = Form(...),
    code: str = Form(...),
    language: str = Form("python"),
    custom_input: str = Form(""),
    explanation: str = Form(""),
    timed_mode: str = Form(""),
):
    selected = get_problem(problem_id)
    if language not in SUPPORTED_LANGUAGES:
        language = "python"
    code = code or ""
    custom_input = custom_input or ""
    if len(code) > CODING_MAX_CODE_CHARS:
        return templates.TemplateResponse(
            "coding.html",
            coding_context_payload(
                request,
                selected["id"],
                language=language,
                code=code[:CODING_MAX_CODE_CHARS],
                premium_notice=f"Code too large. Max {CODING_MAX_CODE_CHARS} characters.",
            ),
        )
    if len(custom_input) > CODING_MAX_CUSTOM_INPUT_CHARS:
        custom_input = custom_input[:CODING_MAX_CUSTOM_INPUT_CHARS]
    timed_state = _apply_timed_mode_selection(request, selected["id"], timed_mode)
    request.session[f"lang_{selected['id']}"] = language
    request.session[f"code_{selected['id']}_{language}"] = code
    request.session[f"custom_input_{selected['id']}"] = custom_input
    result = evaluate_submission(selected, code, language=language, mode="run", custom_input=custom_input)
    attempts = request.session.get("coding_attempts", [])
    attempts.insert(
        0,
        {
            "problem_id": selected["id"],
            "title": selected["title"],
            "language": language,
            "status": result["status"],
            "score": f"{result['passed']}/{result['total']}",
            "runtime_ms": result["runtime_ms"],
            "mode": "run",
            "timestamp": int(time.time()),
        },
    )
    request.session["coding_attempts"] = attempts[:30]
    save_submission(
        problem_id=selected["id"],
        language=language,
        mode="run",
        status=result["status"],
        passed=result["passed"],
        total=result["total"],
        runtime_ms=result["runtime_ms"],
        user_email=request.session.get("user_email", ""),
        explanation=explanation,
    )
    save_attempt_timeline(
        problem_id=selected["id"],
        language=language,
        mode="run",
        status=result["status"],
        passed=result["passed"],
        total=result["total"],
        runtime_ms=result["runtime_ms"],
        code=code,
        user_email=request.session.get("user_email", ""),
        explanation=explanation,
        result=result,
    )
    log_event(
        "coding_run",
        "coding_platform",
        role=selected["title"],
        metadata={"status": result["status"], "score": f"{result['passed']}/{result['total']}", "language": language},
    )
    return templates.TemplateResponse(
        "coding.html",
        coding_context_payload(
            request,
            selected["id"],
            language=language,
            code=code,
            result=result,
            last_custom_input=custom_input,
            explanation=explanation,
            timed_mode=timed_mode,
            timed_state=timed_state,
            followups=coding_followup_questions(selected, code, language=language),
            editorial=editorial_bundle(selected, result, code, language=language),
        ),
    )


@router.post("/coding/submit", response_class=HTMLResponse)
def coding_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    problem_id: str = Form(...),
    code: str = Form(...),
    language: str = Form("python"),
    explanation: str = Form(""),
    timed_mode: str = Form(""),
    idem_key: str = Form(""),
):
    selected = get_problem(problem_id)
    if language not in SUPPORTED_LANGUAGES:
        language = "python"
    code = code or ""
    if len(code) > CODING_MAX_CODE_CHARS:
        return templates.TemplateResponse(
            "coding.html",
            coding_context_payload(
                request,
                selected["id"],
                language=language,
                code=code[:CODING_MAX_CODE_CHARS],
                premium_notice=f"Code too large. Max {CODING_MAX_CODE_CHARS} characters.",
            ),
        )
    timed_state = _apply_timed_mode_selection(request, selected["id"], timed_mode)
    if timed_state.get("enabled") and timed_state.get("expired"):
        return templates.TemplateResponse(
            "coding.html",
            coding_context_payload(
                request,
                selected["id"],
                language=language,
                code=code,
                explanation=explanation,
                timed_mode=timed_mode,
                timed_state=timed_state,
                premium_notice="Timed interview mode expired. Start a new timed session to submit.",
            ),
        )
    if timed_state.get("enabled") and timed_state.get("submitted"):
        return templates.TemplateResponse(
            "coding.html",
            coding_context_payload(
                request,
                selected["id"],
                language=language,
                code=code,
                explanation=explanation,
                timed_mode=timed_mode,
                timed_state=timed_state,
                premium_notice="Timed interview mode allows only one submit attempt.",
            ),
        )
    cached = fetch_idempotent_response(idem_key)
    if cached:
        return templates.TemplateResponse(
            "coding.html",
            coding_context_payload(
                request,
                selected["id"],
                language=language,
                code=code,
                result=cached,
                explanation=explanation,
                timed_mode=timed_mode,
                timed_state=timed_state,
                followups=coding_followup_questions(selected, code, language=language),
                code_review=review_code_heuristic(selected, code, cached, language=language),
                editorial=editorial_bundle(selected, cached, code, language=language),
            ),
        )
    request.session[f"lang_{selected['id']}"] = language
    request.session[f"code_{selected['id']}_{language}"] = code
    if CODING_ASYNC_JUDGE:
        job_id = enqueue_judge_job(
            user_email=request.session.get("user_email", ""),
            problem_id=selected["id"],
            language=language,
            mode="submit",
            code_text=code,
            custom_input="",
            explanation=explanation,
            idem_key=idem_key,
            timed_mode=timed_mode,
        )
        background_tasks.add_task(process_judge_job, job_id)
        if timed_state.get("enabled"):
            _mark_timed_mode_submitted(request, selected["id"], job_id=job_id)
            timed_state = _timed_mode_state(request, selected["id"])
        log_event(
            "coding_submit_queued",
            "coding_platform",
            role=selected["title"],
            metadata={"job_id": job_id, "language": language},
        )
        return templates.TemplateResponse(
            "coding.html",
            coding_context_payload(
                request,
                selected["id"],
                language=language,
                code=code,
                explanation=explanation,
                timed_mode=timed_mode,
                timed_state=timed_state,
                judge_job={"job_id": job_id, "status": "queued", "problem_id": selected["id"], "language": language},
            ),
        )

    result = evaluate_submission(selected, code, language=language, mode="submit")
    attempts = request.session.get("coding_attempts", [])
    attempts.insert(
        0,
        {
            "problem_id": selected["id"],
            "title": selected["title"],
            "language": language,
            "status": result["status"],
            "score": f"{result['passed']}/{result['total']}",
            "runtime_ms": result["runtime_ms"],
            "mode": "submit",
            "timestamp": int(time.time()),
        },
    )
    request.session["coding_attempts"] = attempts[:30]
    save_submission(
        problem_id=selected["id"],
        language=language,
        mode="submit",
        status=result["status"],
        passed=result["passed"],
        total=result["total"],
        runtime_ms=result["runtime_ms"],
        user_email=request.session.get("user_email", ""),
        explanation=explanation,
        session_idem=idem_key,
    )
    save_attempt_timeline(
        problem_id=selected["id"],
        language=language,
        mode="submit",
        status=result["status"],
        passed=result["passed"],
        total=result["total"],
        runtime_ms=result["runtime_ms"],
        code=code,
        user_email=request.session.get("user_email", ""),
        explanation=explanation,
        result=result,
    )
    store_idempotent_response(
        idem_key=idem_key,
        user_email=request.session.get("user_email", ""),
        problem_id=selected["id"],
        language=language,
        mode="submit",
        response=result,
    )
    if timed_state.get("enabled"):
        _mark_timed_mode_submitted(request, selected["id"])
        timed_state = _timed_mode_state(request, selected["id"])
    log_event(
        "coding_submit",
        "coding_platform",
        role=selected["title"],
        metadata={"status": result["status"], "score": f"{result['passed']}/{result['total']}", "language": language},
    )
    return templates.TemplateResponse(
        "coding.html",
        coding_context_payload(
            request,
            selected["id"],
            language=language,
            code=code,
            result=result,
            explanation=explanation,
            timed_mode=timed_mode,
            timed_state=timed_state,
            followups=coding_followup_questions(selected, code, language=language),
            code_review=review_code_heuristic(selected, code, result, language=language),
            editorial=editorial_bundle(selected, result, code, language=language),
        ),
    )


@router.get("/coding/judge-status/{job_id}")
def coding_judge_status(request: Request, job_id: str):
    job = get_judge_job(job_id, request.session.get("user_email", ""))
    if not job:
        return JSONResponse({"ok": False, "status": "not_found"}, status_code=404)
    status = str(job.get("status") or "queued")
    payload: Dict[str, Any] = {"ok": True, "status": status, "job_id": job_id}
    if status == "completed":
        pid = str(job.get("problem_id") or "")
        lang = str(job.get("language") or "python")
        payload["redirect_url"] = f"/coding?problem={pid}&language={lang}&job_id={job_id}"
    elif status == "failed":
        payload["error"] = str(job.get("error_text") or "Judge failed.")
    return JSONResponse(payload)


@router.post("/coding/timed/reset")
def coding_timed_reset(request: Request, problem_id: str = Form(...)):
    selected = get_problem(problem_id)
    _clear_timed_mode(request, selected["id"])
    return RedirectResponse(f"/coding?problem={selected['id']}", status_code=303)


@router.post("/coding/hint", response_class=HTMLResponse)
def coding_hint(
    request: Request,
    problem_id: str = Form(...),
    code: str = Form(""),
    language: str = Form("python"),
    level: int = Form(1),
):
    selected = get_problem(problem_id)
    timed_state = _timed_mode_state(request, selected["id"])
    if timed_state.get("enabled") and not timed_state.get("expired"):
        return templates.TemplateResponse(
            "coding.html",
            coding_context_payload(
                request,
                selected["id"],
                language=language,
                code=code,
                timed_state=timed_state,
                premium_notice="Hints are disabled in timed interview mode.",
            ),
        )
    previous = evaluate_submission(selected, code or "", language=language, mode="run", custom_input="")
    hint = hint_ladder(selected, code or "", previous, level=level)
    save_attempt_timeline(
        problem_id=selected["id"],
        language=language,
        mode="hint",
        status="Hint Viewed",
        passed=int(previous.get("passed") or 0),
        total=int(previous.get("total") or 0),
        runtime_ms=float(previous.get("runtime_ms") or 0.0),
        code=code or "",
        user_email=request.session.get("user_email", ""),
        explanation="",
        result=previous,
    )
    return templates.TemplateResponse(
        "coding.html",
        coding_context_payload(
            request,
            selected["id"],
            language=language,
            code=code,
            result=previous,
            hint_result=hint,
            timed_state=timed_state,
            followups=coding_followup_questions(selected, code, language=language),
            editorial=editorial_bundle(selected, previous, code or "", language=language),
        ),
    )


@router.post("/coding/interviewer", response_class=HTMLResponse)
def coding_interviewer(
    request: Request,
    problem_id: str = Form(...),
    code: str = Form(""),
    language: str = Form("python"),
):
    selected = get_problem(problem_id)
    timed_state = _timed_mode_state(request, selected["id"])
    followups = coding_followup_questions(selected, code, language=language)
    save_attempt_timeline(
        problem_id=selected["id"],
        language=language,
        mode="interviewer",
        status="Interviewer Follow-up",
        passed=0,
        total=0,
        runtime_ms=0.0,
        code=code or "",
        user_email=request.session.get("user_email", ""),
        explanation="",
        result={},
    )
    return templates.TemplateResponse(
        "coding.html",
        coding_context_payload(
            request,
            selected["id"],
            language=language,
            code=code,
            followups=followups,
            interviewer_mode=True,
            timed_state=timed_state,
        ),
    )


