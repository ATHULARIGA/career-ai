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


@router.get("/admin/users", response_class=HTMLResponse)
def admin_users_page(request: Request, q: str = "", role: str = "", msg: str = "", error: str = ""):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")

    users_list = get_admin_users_list(search=q, role_filter=role)
    payload = admin_context_payload(request)

    current_email = (request.session.get("user_email") or "").strip().lower()
    current_user_id = request.session.get("user_id")

    return templates.TemplateResponse(
        request=request,
        name="admin_users.html",
        context={
            **payload,
            "users": users_list,
            "search_query": q,
            "role_filter": role,
            "current_email": current_email,
            "current_user_id": current_user_id,
            "active_admin_page": "users",
            "flash_msg": msg,
            "flash_error": error,
        },
    )


@router.post("/admin/users/{user_id}/role")
def admin_update_user_role(
    user_id: int,
    request: Request,
    new_role: str = Form(...),
):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")

    actor = request.session.get("user_email") or request.session.get("admin_user") or "admin"
    current_id = request.session.get("user_id")

    # Safeguard against self-demotion
    if current_id and int(current_id) == int(user_id) and new_role != "admin":
        import urllib.parse
        return RedirectResponse("/admin/users?error=" + urllib.parse.quote("You cannot revoke your own admin access."), status_code=303)

    ok, msg = update_user_role(user_id, new_role, actor)
    import urllib.parse
    param = "msg" if ok else "error"
    return RedirectResponse(f"/admin/users?{param}={urllib.parse.quote(msg)}", status_code=303)


@router.post("/admin-login")
def admin_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    website: str = Form(""),
):
    if (website or "").strip():
        return templates.TemplateResponse(
            request=request,
            name="admin_login.html",
            context={"request": request, "error": "Request blocked."},
        )
    blocked, retry = is_rate_limited(request, "admin_login", identity=username, max_attempts=5, window_sec=300, block_sec=900)
    if blocked:
        return templates.TemplateResponse(
            request=request,
            name="admin_login.html",
            context={"request": request, "error": f"Too many attempts. Try again in {retry}s."},
        )

    # 1. Master admin credentials from environment
    admin_username, admin_password, admin_email = get_admin_settings()
    if admin_username and admin_password and username == admin_username and password == admin_password:
        request.session["admin"] = True
        request.session["admin_user"] = admin_username
        request.session["user_role"] = "admin"
        request.session["user_plan"] = "premium"
        record_auth_success(request, "admin_login", identity=username)
        log_audit("admin", "admin_login_success", "Master admin authenticated.")
        return RedirectResponse("/admin", status_code=303)

    # 2. Database user with role='admin'
    import db.backend as db
    conn = db.get_conn()
    cur = conn.cursor()
    db.execute(
        cur,
        "SELECT id, full_name, email, password_hash, role, plan FROM users WHERE (LOWER(email)=? OR LOWER(full_name)=?) AND role='admin'",
        (username.strip().lower(), username.strip().lower()),
    )
    admin_user = cur.fetchone()
    conn.close()

    if admin_user and verify_password(admin_user[3], password):
        request.session["admin"] = True
        request.session["admin_user"] = admin_user[2]
        request.session["user_id"] = int(admin_user[0])
        request.session["user_name"] = admin_user[1]
        request.session["user_email"] = admin_user[2]
        request.session["user_role"] = "admin"
        request.session["user_plan"] = "premium"
        record_auth_success(request, "admin_login", identity=username)
        log_audit("admin", "admin_login_success", f"Admin user {admin_user[2]} authenticated.")
        return RedirectResponse("/admin", status_code=303)

    record_auth_failure(request, "admin_login", identity=username)
    log_audit("admin", "admin_login_failed", f"username={username}")
    return templates.TemplateResponse(
        request=request,
        name="admin_login.html",
        context={"request": request, "error": "Invalid credentials or account does not have admin privileges."},
    )

# ADMIN
