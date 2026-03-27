from fastapi import APIRouter, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import time
from typing import Any, Dict

# Modular imports
from core import templates, logger
from features.shared.config import CODING_MAX_CODE_CHARS, CODING_MAX_CUSTOM_INPUT_CHARS, CODING_ASYNC_JUDGE, DEFAULT_PROBLEMS
from features.shared.analytics import log_event
from features.coding.platform import (
    get_problem,
    get_all_problems,
    company_sets,
    SUPPORTED_LANGUAGES,
    evaluate_submission,
    save_submission,
    save_attempt_timeline,
    fetch_idempotent_response,
    store_idempotent_response,
    enqueue_judge_job,
    process_judge_job,
    get_judge_job,
    hint_ladder,
    coding_followup_questions,
    editorial_bundle,
    review_code_heuristic,
    coding_context_payload,
    _mark_timed_mode_submitted,
    # _apply_timed_mode_selection is now integrated into coding_context_payload or handled locally
)
from features.shared import _timed_mode_state

# Local helper originally in core.py
_TIMED_ALLOWED = {"35", "45"}
def _timed_session_key(problem_id: str) -> str:
    return f"timed_mode_{str(problem_id or '').strip()}"

def _clear_timed_mode(request: Request, problem_id: str) -> None:
    request.session.pop(_timed_session_key(problem_id), None)

def _apply_timed_mode_selection(request: Request, problem_id: str, timed_mode: str) -> dict:
    mode = str(timed_mode or "").strip()
    key = _timed_session_key(problem_id)
    now = int(time.time())
    if mode in _TIMED_ALLOWED:
        state = request.session.get(key) or {}
        if str(state.get("duration_min") or "") != mode:
            state = {"duration_min": int(mode), "start_ts": now, "submitted": False, "job_id": ""}
            request.session[key] = state
    elif mode == "":
        _clear_timed_mode(request, problem_id)
    return _timed_mode_state(request, problem_id)

router = APIRouter()

@router.get("/coding", response_class=HTMLResponse)
def coding_page(request: Request, problem: str = "", language: str = "", job_id: str = ""):
    selected_id = str(problem or DEFAULT_PROBLEMS[0]["id"])
    if language in SUPPORTED_LANGUAGES: request.session[f"lang_{selected_id}"] = language
    extra: Dict[str, Any] = {}
    if job_id:
        job = get_judge_job(job_id, request.session.get("user_email", ""))
        if job and str(job.get("status")) == "completed":
            pid = str(job.get("problem_id") or "")
            selected = get_problem(pid)
            extra.update({"judge_job": job, "result": job.get("result"), "code": job.get("code_text")})
    return templates.TemplateResponse(request=request, name="coding.html", context=coding_context_payload(request, selected_id, **extra))

@router.get("/coding/problems", response_class=HTMLResponse)
def coding_problems_list(request: Request):
     problems = get_all_problems()
     return templates.TemplateResponse(request=request, name="coding_problems.html", context={"request": request, "problems": problems, "company_sets": company_sets()})

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
    if language not in SUPPORTED_LANGUAGES: language = "python"
    code = code or ""
    custom_input = custom_input or ""
    
    if len(code) > CODING_MAX_CODE_CHARS:
        return templates.TemplateResponse(request=request, name="coding.html", context=coding_context_payload(
            request, selected["id"], language=language, code=code[:CODING_MAX_CODE_CHARS],
            premium_notice=f"Code too large. Max {CODING_MAX_CODE_CHARS} characters."
        ))

    if len(custom_input) > CODING_MAX_CUSTOM_INPUT_CHARS:
        custom_input = custom_input[:CODING_MAX_CUSTOM_INPUT_CHARS]
        
    timed_state = _apply_timed_mode_selection(request, selected["id"], timed_mode)
    request.session[f"lang_{selected['id']}"] = language
    request.session[f"code_{selected['id']}_{language}"] = code
    request.session[f"custom_input_{selected['id']}"] = custom_input
    
    result = evaluate_submission(selected, code, language=language, mode="run", custom_input=custom_input)
    attempts = request.session.get("coding_attempts", [])
    attempts.insert(0, {"problem_id": selected["id"], "title": selected["title"], "language": language, "status": result["status"], "score": f"{result['passed']}/{result['total']}", "runtime_ms": result["runtime_ms"], "mode": "run", "timestamp": int(time.time())})
    request.session["coding_attempts"] = attempts[:30]
    
    save_submission(problem_id=selected["id"], language=language, mode="run", status=result["status"], passed=result["passed"], total=result["total"], runtime_ms=result["runtime_ms"], user_email=request.session.get("user_email", ""), explanation=explanation)
    save_attempt_timeline(problem_id=selected["id"], language=language, mode="run", status=result["status"], passed=result["passed"], total=result["total"], runtime_ms=result["runtime_ms"], code=code, user_email=request.session.get("user_email", ""), explanation=explanation, result=result)
    
    log_event("coding_run", "coding_platform", role=selected["title"], metadata={"status": result["status"], "language": language})
    
    return templates.TemplateResponse(request=request, name="coding.html", context=coding_context_payload(
        request, selected["id"], language=language, code=code, result=result, last_custom_input=custom_input, explanation=explanation, timed_mode=timed_mode, timed_state=timed_state,
        followups=coding_followup_questions(selected, code, language=language),
        editorial=editorial_bundle(selected, result, code, language=language)
    ))

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
    if language not in SUPPORTED_LANGUAGES: language = "python"
    code = code or ""
    
    if len(code) > CODING_MAX_CODE_CHARS:
        return templates.TemplateResponse(request=request, name="coding.html", context=coding_context_payload(request, selected["id"], language=language, code=code[:CODING_MAX_CODE_CHARS], premium_notice="Code too large."))

    timed_state = _apply_timed_mode_selection(request, selected["id"], timed_mode)
    if timed_state.get("enabled") and (timed_state.get("expired") or timed_state.get("submitted")):
        return templates.TemplateResponse(request=request, name="coding.html", context=coding_context_payload(request, selected["id"], language=language, code=code, premium_notice="Timed session issue."))

    cached = fetch_idempotent_response(idem_key)
    if cached:
        return templates.TemplateResponse(request=request, name="coding.html", context=coding_context_payload(request, selected["id"], language=language, code=code, result=cached, followups=coding_followup_questions(selected, code, language=language), code_review=review_code_heuristic(selected, code, cached, language=language), editorial=editorial_bundle(selected, cached, code, language=language)))

    request.session[f"lang_{selected['id']}"] = language
    request.session[f"code_{selected['id']}_{language}"] = code
    
    if CODING_ASYNC_JUDGE:
        job_id = enqueue_judge_job(user_email=request.session.get("user_email", ""), problem_id=selected["id"], language=language, mode="submit", code_text=code, custom_input="", explanation=explanation, idem_key=idem_key, timed_mode=timed_mode)
        background_tasks.add_task(process_judge_job, job_id)
        if timed_state.get("enabled"): _mark_timed_mode_submitted(request, selected["id"], job_id=job_id)
        return templates.TemplateResponse(request=request, name="coding.html", context=coding_context_payload(request, selected["id"], language=language, code=code, judge_job={"job_id": job_id, "status": "queued"}))

    result = evaluate_submission(selected, code, language=language, mode="submit")
    save_submission(problem_id=selected["id"], language=language, mode="submit", status=result["status"], passed=result["passed"], total=result["total"], runtime_ms=result["runtime_ms"], user_email=request.session.get("user_email", ""), explanation=explanation, session_idem=idem_key)
    store_idempotent_response(idem_key=idem_key, user_email=request.session.get("user_email", ""), problem_id=selected["id"], language=language, mode="submit", response=result)
    
    return templates.TemplateResponse(request=request, name="coding.html", context=coding_context_payload(request, selected["id"], language=language, code=code, result=result, followups=coding_followup_questions(selected, code, language=language), code_review=review_code_heuristic(selected, code, result, language=language), editorial=editorial_bundle(selected, result, code, language=language)))

@router.get("/coding/judge-status/{job_id}")
def coding_judge_status(request: Request, job_id: str):
    job = get_judge_job(job_id, request.session.get("user_email", ""))
    if not job: return JSONResponse({"ok": False}, status_code=404)
    status = job.get("status", "queued")
    payload = {"ok": True, "status": status, "job_id": job_id}
    if status == "completed":
        payload["redirect_url"] = f"/coding?problem={job.get('problem_id')}&language={job.get('language')}&job_id={job_id}"
    return JSONResponse(payload)

@router.post("/coding/timed/reset")
def coding_timed_reset(request: Request, problem_id: str = Form(...)):
    _clear_timed_mode(request, problem_id)
    return RedirectResponse(f"/coding?problem={problem_id}", status_code=303)

@router.post("/coding/hint", response_class=HTMLResponse)
def coding_hint(request: Request, problem_id: str = Form(...), code: str = Form(""), language: str = Form("python"), level: int = Form(1)):
    selected = get_problem(problem_id)
    timed_state = _timed_mode_state(request, selected["id"])
    if timed_state.get("enabled") and not timed_state.get("expired"):
        return templates.TemplateResponse(request=request, name="coding.html", context=coding_context_payload(request, selected["id"], language=language, code=code, premium_notice="Hints disabled in timed mode."))
    
    previous = evaluate_submission(selected, code or "", language=language, mode="run")
    hint = hint_ladder(selected, code or "", previous, level=level)
    return templates.TemplateResponse(request=request, name="coding.html", context=coding_context_payload(request, selected["id"], language=language, code=code, result=previous, hint_result=hint, followups=coding_followup_questions(selected, code, language=language), editorial=editorial_bundle(selected, previous, code or "", language=language)))
