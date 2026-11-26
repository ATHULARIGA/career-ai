"""
Versioned JSON API v1 endpoints for Interview Resumes & Technology Cheat Sheets.
Uses Pydantic request validation, repository persistence, and domain exceptions.
"""

import re
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from core.exceptions import NotFoundError, RateLimitError, ValidationError
from core.helpers import get_selectable_resumes_for_user, resolve_resume_context
from core.security import is_rate_limited, record_auth_failure
from db.repositories.cheatsheets import (
    delete_user_cheatsheet,
    get_user_cheatsheets,
    save_user_cheatsheet,
    update_cheatsheet_revised,
)
from schemas.interview import (
    CheatsheetAddRequest,
    CheatsheetReviseRequest,
    SelectResumeRequest,
)
from services.interview.cheatsheet_generator import (
    extract_technologies_from_resume,
    get_cheatsheet_for_technology,
)

router = APIRouter(prefix="/interview", tags=["interview-v1"])


@router.get("/resumes", response_class=JSONResponse)
def v1_interview_resumes(request: Request) -> JSONResponse:
    """Returns all selectable resumes and active selection for the user."""
    user_email = (request.session.get("user_email") or "").strip().lower()
    resumes = get_selectable_resumes_for_user(user_email, request)
    selected_id = request.session.get("selected_resume_id", "")
    available_ids = [r["id"] for r in resumes]
    if selected_id not in available_ids:
        selected_id = available_ids[0] if available_ids else "latest"
    return JSONResponse({"resumes": resumes, "selected_resume_id": selected_id})


@router.post("/select-resume", response_class=JSONResponse)
def v1_interview_select_resume(request: Request, payload: SelectResumeRequest) -> JSONResponse:
    """Switches active resume context and returns tailored technologies & cheat sheet."""
    resume_id = payload.resume_id.strip()
    if resume_id == "__upload__":
        raise ValidationError("Upload option selected, please upload a file")

    user_email = (request.session.get("user_email") or "").strip().lower()
    selectable = get_selectable_resumes_for_user(user_email, request)
    if resume_id not in [r["id"] for r in selectable]:
        raise NotFoundError("Selected resume not found")

    request.session["selected_resume_id"] = resume_id
    report, resume_text, target_role = resolve_resume_context(resume_id, user_email, request)
    resume_techs = extract_technologies_from_resume(resume_text, report)
    active_tech = resume_techs[0] if resume_techs else "FastAPI"
    cheatsheet = get_cheatsheet_for_technology(active_tech, resume_text=resume_text, target_role=target_role)
    cheatsheet["selected_resume_id"] = resume_id

    return JSONResponse({
        "success": True,
        "selected_resume_id": resume_id,
        "target_role": target_role,
        "resume_technologies": resume_techs,
        "active_technology": active_tech,
        "cheatsheet": cheatsheet,
    })


@router.get("/technologies", response_class=JSONResponse)
def v1_interview_technologies(request: Request, resume_id: str = "") -> JSONResponse:
    """Returns detected resume technologies, custom technologies, and revision progress."""
    user_email = (request.session.get("user_email") or "").strip().lower()
    selected_id = resume_id.strip() or request.session.get("selected_resume_id", "")
    resume_report, resume_text, target_role = resolve_resume_context(selected_id, user_email, request)

    resume_techs = extract_technologies_from_resume(resume_text, resume_report)
    excluded = {x.lower() for x in request.session.get("excluded_technologies", [])}
    resume_techs = [t for t in resume_techs if t.lower() not in excluded]

    saved_records = get_user_cheatsheets(user_email) if user_email else request.session.get("session_custom_cheatsheets", [])
    custom_techs = [
        c["tech_name"]
        for c in saved_records
        if isinstance(c, dict) and c.get("is_custom") and c.get("tech_name") and c["tech_name"].lower() not in excluded
    ]
    saved_revised: dict[str, Any] = {
        c["tech_name"]: c.get("revised_indices", [])
        for c in saved_records
        if isinstance(c, dict) and c.get("tech_name")
    }
    return JSONResponse({
        "resume_technologies": resume_techs,
        "custom_technologies": custom_techs,
        "saved_revised": saved_revised,
        "target_role": target_role,
        "selected_resume_id": selected_id,
        "has_resume": bool(resume_text),
    })


@router.get("/cheatsheet", response_class=JSONResponse)
def v1_interview_cheatsheet(request: Request, tech: str = "", resume_id: str = "") -> JSONResponse:
    """Returns a resume-tailored cheat sheet for the requested technology."""
    tech_name = tech.strip()
    if not tech_name:
        raise ValidationError("Technology name is required")

    user_email = (request.session.get("user_email") or "").strip().lower()
    selected_id = resume_id.strip() or request.session.get("selected_resume_id", "")
    _report, resume_text, target_role = resolve_resume_context(selected_id, user_email, request)

    saved_records = get_user_cheatsheets(user_email) if user_email else request.session.get("session_custom_cheatsheets", [])
    revised_indices: list[int] = []
    cached_payload = None
    for rec in saved_records:
        if rec.get("tech_name", "").lower() == tech_name.lower():
            revised_indices = rec.get("revised_indices", [])
            cs_obj = rec.get("cheatsheet")
            if (
                isinstance(cs_obj, dict)
                and cs_obj.get("cards")
                and cs_obj.get("deck_version", 1) >= 2
                and len(cs_obj.get("cards", [])) >= 12
                and cs_obj.get("selected_resume_id", "") == selected_id
            ):
                cached_payload = dict(cs_obj)
            break

    if cached_payload:
        result = cached_payload
    else:
        result = get_cheatsheet_for_technology(tech_name, resume_text=resume_text, target_role=target_role)
        result["selected_resume_id"] = selected_id
        if user_email:
            save_user_cheatsheet(user_email, result["tech_name"], result, is_custom=False, revised_indices=revised_indices)

    result["revised_indices"] = revised_indices
    return JSONResponse(result)


@router.post("/cheatsheet/add", response_class=JSONResponse)
def v1_interview_cheatsheet_add(request: Request, body: CheatsheetAddRequest) -> JSONResponse:
    """Adds a custom technology and generates a cheat sheet tailored to the selected resume."""
    user_email = (request.session.get("user_email") or "").strip().lower()
    blocked, retry = is_rate_limited(
        request,
        "cheatsheet_add",
        identity=user_email or "anon",
        max_attempts=25,
        window_sec=300,
        block_sec=300,
    )
    if blocked:
        raise RateLimitError(retry_after=retry)
    record_auth_failure(request, "cheatsheet_add", identity=user_email or "anon", window_sec=300)

    clean_tech = re.sub(r"[^\w\s\.\+\#\-\/]", "", body.tech.strip()).strip()
    if not clean_tech:
        raise ValidationError("Invalid technology name")

    selected_id = body.resume_id.strip() or request.session.get("selected_resume_id", "")
    _report, resume_text, target_role = resolve_resume_context(selected_id, user_email, request)
    result = get_cheatsheet_for_technology(clean_tech, resume_text=resume_text, target_role=target_role)
    result["revised_indices"] = []
    result["selected_resume_id"] = selected_id

    if user_email:
        save_user_cheatsheet(user_email, result["tech_name"], result, is_custom=True, revised_indices=[])
    return JSONResponse(result)


@router.post("/cheatsheet/revise", response_class=JSONResponse)
def v1_interview_cheatsheet_revise(request: Request, body: CheatsheetReviseRequest) -> JSONResponse:
    """Updates card revision status for a technology cheat sheet."""
    user_email = (request.session.get("user_email") or "").strip().lower()
    tech_name = body.tech.strip()
    revised_list: list[int] = []

    if user_email:
        for rec in get_user_cheatsheets(user_email):
            if rec.get("tech_name", "").lower() == tech_name.lower():
                revised_list = list(rec.get("revised_indices", []))
                break
        if body.revised and body.card_index not in revised_list:
            revised_list.append(body.card_index)
        elif not body.revised and body.card_index in revised_list:
            revised_list.remove(body.card_index)
        update_cheatsheet_revised(user_email, tech_name, sorted(revised_list))
    else:
        key = f"revised_{tech_name.lower()}"
        revised_list = list(request.session.get(key, []))
        if body.revised and body.card_index not in revised_list:
            revised_list.append(body.card_index)
        elif not body.revised and body.card_index in revised_list:
            revised_list.remove(body.card_index)
        request.session[key] = sorted(revised_list)

    return JSONResponse({"success": True, "revised_indices": sorted(revised_list)})


@router.delete("/cheatsheet", response_class=JSONResponse)
def v1_interview_cheatsheet_delete(request: Request, tech: str = "") -> JSONResponse:
    """Deletes or hides a technology cheat sheet for the current user/session."""
    tech_name = tech.strip()
    if not tech_name:
        raise ValidationError("Technology name is required")

    user_email = (request.session.get("user_email") or "").strip().lower()
    excluded = list(request.session.get("excluded_technologies", []))
    if tech_name.lower() not in [x.lower() for x in excluded]:
        excluded.append(tech_name)
    request.session["excluded_technologies"] = excluded

    if user_email:
        delete_user_cheatsheet(user_email, tech_name)
    return JSONResponse({"success": True, "deleted": tech_name})
