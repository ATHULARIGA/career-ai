from fastapi import APIRouter, Request, Form, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
from core import *

router = APIRouter()

@router.post("/admin/coding-problem/add")
def admin_add_coding_problem(
    request: Request,
    title: str = Form(...),
    difficulty: str = Form("Easy"),
    tags: str = Form(""),
    description: str = Form(...),
    constraints: str = Form(""),
    examples: str = Form(""),
    sample_tests: str = Form(...),
    hidden_tests: str = Form(""),
    starter_py: str = Form(""),
    starter_js: str = Form(""),
    starter_java: str = Form(""),
    starter_cpp: str = Form(""),
):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")

    payload = _parse_problem_admin_payload(
        title=title,
        difficulty=difficulty,
        tags=tags,
        description=description,
        constraints=constraints,
        examples=examples,
        sample_tests=sample_tests,
        hidden_tests=hidden_tests,
        starter_py=starter_py,
        starter_js=starter_js,
        starter_java=starter_java,
        starter_cpp=starter_cpp,
    )
    if not payload["sample_tests"]:
        log_audit("admin", "coding_problem_add_failed", "sample_tests_empty")
        return RedirectResponse("/admin/coding", status_code=303)

    problem_id = add_custom_problem(
        title=payload["title"],
        difficulty=payload["difficulty"],
        description=payload["description"],
        tags=payload["tags"],
        constraints=payload["constraints"],
        examples=payload["examples"],
        sample_tests=payload["sample_tests"],
        hidden_tests=payload["hidden_tests"],
        starter_py=payload["starter_py"],
        starter_js=payload["starter_js"],
        starter_java=payload["starter_java"],
        starter_cpp=payload["starter_cpp"],
    )
    log_audit("admin", "coding_problem_added", f"id={problem_id},title={title.strip()}")
    return RedirectResponse("/admin/coding", status_code=303)


@router.post("/admin/coding-problem/{problem_id}/edit")
def admin_edit_coding_problem(
    problem_id: str,
    request: Request,
    title: str = Form(...),
    difficulty: str = Form("Easy"),
    tags: str = Form(""),
    description: str = Form(...),
    constraints: str = Form(""),
    examples: str = Form(""),
    sample_tests: str = Form(...),
    hidden_tests: str = Form(""),
    starter_py: str = Form(""),
    starter_js: str = Form(""),
    starter_java: str = Form(""),
    starter_cpp: str = Form(""),
):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    payload = _parse_problem_admin_payload(
        title=title,
        difficulty=difficulty,
        tags=tags,
        description=description,
        constraints=constraints,
        examples=examples,
        sample_tests=sample_tests,
        hidden_tests=hidden_tests,
        starter_py=starter_py,
        starter_js=starter_js,
        starter_java=starter_java,
        starter_cpp=starter_cpp,
    )
    if not payload["sample_tests"]:
        log_audit("admin", "coding_problem_edit_failed", f"id={problem_id}|sample_tests_empty")
        return RedirectResponse("/admin/coding", status_code=303)
    changed = update_custom_problem(
        problem_id=problem_id,
        title=payload["title"],
        difficulty=payload["difficulty"],
        description=payload["description"],
        tags=payload["tags"],
        constraints=payload["constraints"],
        examples=payload["examples"],
        sample_tests=payload["sample_tests"],
        hidden_tests=payload["hidden_tests"],
        starter_py=payload["starter_py"],
        starter_js=payload["starter_js"],
        starter_java=payload["starter_java"],
        starter_cpp=payload["starter_cpp"],
    )
    log_audit("admin", "coding_problem_edited", f"id={problem_id},changed={changed}")
    return RedirectResponse("/admin/coding", status_code=303)


@router.post("/admin/coding-problem/{problem_id}/delete")
def admin_delete_coding_problem(problem_id: str, request: Request):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    changed = delete_custom_problem(problem_id)
    log_audit("admin", "coding_problem_deleted", f"id={problem_id},changed={changed}")
    return RedirectResponse("/admin/coding", status_code=303)


@router.get("/admin/coding/export")
def admin_export_coding_problems(request: Request, format: str = "json"):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    fmt = (format or "json").strip().lower()
    if fmt == "csv":
        content = export_problems_csv()
        return PlainTextResponse(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=coding_problems.csv"},
        )
    content = export_problems_json()
    return PlainTextResponse(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=coding_problems.json"},
    )


@router.post("/admin/coding/import")
async def admin_import_coding_problems(request: Request, file: UploadFile = File(...)):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    raw = (await file.read()).decode("utf-8", errors="ignore")
    stats = import_problems_from_json(raw)
    msg = f"created={stats.get('created', 0)},updated={stats.get('updated', 0)},failed={stats.get('failed', 0)}"
    log_audit("admin", "coding_problem_imported", msg)
    return RedirectResponse(f"/admin/coding?import={msg}", status_code=303)


@router.post("/admin-login")
def admin_login(request: Request,
                username: str = Form(...),
                password: str = Form(...),
                website: str = Form("")):
    if (website or "").strip():
        return templates.TemplateResponse(
            request=request,
            name="admin_login.html",
            context={
                "request": request,
                "error": "Request blocked."
            }
        )
    blocked, retry = is_rate_limited(request, "admin_login", identity=username, max_attempts=5, window_sec=300, block_sec=900)
    if blocked:
        return templates.TemplateResponse(
            request=request,
            name="admin_login.html",
            context={
                "request": request,
                "error": f"Too many attempts. Try again in {retry}s."
            }
        )
    admin_username, admin_password, admin_email = get_admin_settings()
    if not admin_username or not admin_password or not admin_email:
        log_audit("admin", "admin_login_blocked", "admin_env_not_configured")
        return templates.TemplateResponse(
            request=request,
            name="admin_login.html",
            context={
                "request": request,
                "error": "Admin access is not configured. Set ADMIN_USERNAME, ADMIN_PASSWORD and ADMIN_EMAIL."
            }
        )

    user_email = (request.session.get("user_email") or "").strip().lower()
    if user_email != admin_email:
        record_auth_failure(request, "admin_login", identity=username)
        log_audit("admin", "admin_login_denied", f"user_email={user_email}")
        return templates.TemplateResponse(
            request=request,
            name="admin_login.html",
            context={
                "request": request,
                "error": "This account is not allowed for admin access."
            }
        )

    if username == admin_username and password == admin_password:
        request.session["admin"] = True
        request.session["admin_user"] = admin_username
        request.session["user_role"] = "admin"
        request.session["user_plan"] = "premium"
        record_auth_success(request, "admin_login", identity=username)
        log_audit("admin", "admin_login_success", "Admin authenticated.")
        return RedirectResponse("/admin", status_code=303)

    record_auth_failure(request, "admin_login", identity=username)
    log_audit("admin", "admin_login_failed", f"username={username}")
    return templates.TemplateResponse(
        request=request,
        name="admin_login.html",
        context={
            "request": request,
            "error": "Invalid credentials"
        }
    )

# ADMIN
