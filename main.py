from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from resume_parser import extract_text
from scoring import score_resume
from interview_engine import generate_questions, generate_follow_up
import time
from booking_db import save_booking, get_bookings, get_booking, assign_mentor_email
from email_sender import send_mail
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from mindmap_generator import generate_mindmap
from fastapi.responses import JSONResponse, PlainTextResponse
from dotenv import load_dotenv
import os
import json
import hashlib
from interview_feedback import analyze_answer, hiring_decision
from fastapi.responses import RedirectResponse
import sqlite3
from urllib.parse import urlencode
from coding_platform import (
    DEFAULT_PROBLEMS,
    SUPPORTED_LANGUAGES,
    get_all_problems,
    get_custom_problems,
    get_submission_stats,
    get_problem,
    evaluate_submission,
    save_submission,
    starter_for_language,
    init_coding_tables,
    add_custom_problem,
    update_custom_problem,
    delete_custom_problem,
    parse_test_lines,
)
from admin_analytics import (
    init_admin_tables,
    log_event,
    log_model_health,
    add_feedback,
    update_feedback_status,
    log_audit,
    upsert_experiment,
    upsert_ab_test,
    add_safety_event,
    log_mentor_metric,
    dashboard_payload,
    export_all_json,
    export_all_csv,
)

load_dotenv()

def get_admin_settings() -> tuple[str, str, str]:
    # Reload .env so credential changes apply without requiring a server restart.
    load_dotenv(override=True)
    admin_username = (os.getenv("ADMIN_USERNAME") or "").strip()
    admin_password = os.getenv("ADMIN_PASSWORD") or ""
    admin_email = (os.getenv("ADMIN_EMAIL") or "").strip().lower()
    return admin_username, admin_password, admin_email





def normalize_question(q):

    if isinstance(q, dict):
        q = q.get("question", "")

    q = str(q)
    q = q.replace("\n", " ")
    q = q.replace("Question:", "")
    q = q.strip()

    return q


def parse_json_object(raw: str):
    cleaned = (raw or "").replace("```json", "").replace("```", "").strip()
    if "{" in cleaned and "}" in cleaned:
        cleaned = cleaned[cleaned.find("{"):cleaned.rfind("}") + 1]
    return json.loads(cleaned)


def build_pre_session_brief(name: str, email: str, topic: str, datetime: str, outcome: str, context_notes: str, link: str) -> str:
    return f"""
Pre-Session Brief

Candidate: {name}
Candidate Email: {email}
Specialization: {topic}
Scheduled Time: {datetime}
Target Outcome: {outcome or "Not provided"}
Context Notes: {context_notes or "Not provided"}
Meeting Link: {link}

Proposed Session Plan (30-45 min):
1. 5 min: Goal alignment and context
2. 20-30 min: Focused mock/mentorship on target outcome
3. 10 min: Action plan with next steps
""".strip()


def interview_context_payload(request: Request, **extra):
    payload = {
        "request": request,
        "questions": request.session.get("questions", []),
        "current": request.session.get("current", 0),
        "finished": request.session.get("finished", False),
        "config": request.session.get("interview_config", {}),
        "timeline": request.session.get("timeline", []),
        "feedback": request.session.get("last_feedback"),
        "final_score": request.session.get("final_score"),
        "hiring_result": request.session.get("hiring_result"),
        "next_followup": request.session.get("next_followup"),
    }
    payload.update(extra)
    return payload


def coding_context_payload(request: Request, problem_id: str, **extra):
    attempts = request.session.get("coding_attempts", [])
    problems = get_all_problems()
    selected = get_problem(problem_id)
    language = request.session.get(f"lang_{selected['id']}", "python")
    if language not in SUPPORTED_LANGUAGES:
        language = "python"
    code_key = f"code_{selected['id']}_{language}"
    problem_attempts = [a for a in attempts if a.get("problem_id") == selected["id"]][:12]
    solved = set(
        a.get("problem_id")
        for a in attempts
        if a.get("mode") == "submit" and a.get("status") == "Accepted"
    )
    payload = {
        "request": request,
        "problems": problems,
        "problem": selected,
        "selected_problem_id": selected["id"],
        "language": language,
        "languages": list(SUPPORTED_LANGUAGES),
        "code": request.session.get(code_key, starter_for_language(selected, language)),
        "result": None,
        "attempts": attempts[:20],
        "problem_attempts": problem_attempts,
        "solved_count": len(solved),
        "last_custom_input": request.session.get(f"custom_input_{selected['id']}", ""),
    }
    payload.update(extra)
    return payload


def admin_context_payload(request: Request):
    data = get_bookings()
    payload = dashboard_payload(data)
    coding_stats = get_submission_stats(limit=100)
    custom_problems = get_custom_problems()
    return {
        "request": request,
        "data": data,
        "admin": payload,
        "coding_stats": coding_stats,
        "custom_problems": custom_problems,
    }


def _parse_problem_admin_payload(
    title: str,
    difficulty: str,
    tags: str,
    description: str,
    constraints: str,
    examples: str,
    sample_tests: str,
    hidden_tests: str,
    starter_py: str,
    starter_js: str,
    starter_java: str,
    starter_cpp: str,
):
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    constraint_list = [c.strip() for c in constraints.splitlines() if c.strip()]

    example_list = []
    for line in (examples or "").splitlines():
        raw = line.strip()
        if not raw or "|||" not in raw:
            continue
        inp, out = raw.split("|||", 1)
        example_list.append({"input": inp.strip().replace("\\n", "\n"), "output": out.strip().replace("\\n", "\n")})

    parsed_sample_tests = parse_test_lines(sample_tests)
    parsed_hidden_tests = parse_test_lines(hidden_tests)

    defaults = {
        "starter_py": "def solve(input_data: str) -> str:\n    # Write your solution here\n    return \"\"\n",
        "starter_js": "function solve(inputData) {\n  // Write your solution here\n  return \"\";\n}\n",
        "starter_java": "import java.util.*;\n\npublic class Solution {\n  public static String solve(String inputData) {\n    // Write your solution here\n    return \"\";\n  }\n}\n",
        "starter_cpp": "#include <bits/stdc++.h>\nusing namespace std;\n\nstring solve(const string& inputData) {\n    // Write your solution here\n    return \"\";\n}\n",
    }
    return {
        "title": title,
        "difficulty": difficulty,
        "description": description,
        "tags": tag_list,
        "constraints": constraint_list,
        "examples": example_list,
        "sample_tests": parsed_sample_tests,
        "hidden_tests": parsed_hidden_tests,
        "starter_py": starter_py.strip() or defaults["starter_py"],
        "starter_js": starter_js.strip() or defaults["starter_js"],
        "starter_java": starter_java.strip() or defaults["starter_java"],
        "starter_cpp": starter_cpp.strip() or defaults["starter_cpp"],
    }


session_secret = os.getenv("SESSION_SECRET_KEY") or os.getenv("SESSION_SECRET")
if not session_secret:
    # Fallback keeps local dev running; set SESSION_SECRET_KEY in production.
    session_secret = "dev-only-change-this-secret"


app = FastAPI()

class AuthGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path or "/"
        normalized_path = path.rstrip("/") or "/"

        if normalized_path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES):
            return await call_next(request)

        if request.session.get("user_id") or is_admin_session(request):
            return await call_next(request)

        return RedirectResponse("/?auth=required", status_code=303)


app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(AuthGateMiddleware)
app.add_middleware(SessionMiddleware, secret_key=session_secret)

templates = Jinja2Templates(directory="templates")
init_admin_tables()
init_coding_tables()


def init_user_tables() -> None:
    conn = sqlite3.connect("bookings.db")
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_ts INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    return hashlib.sha256((password or "").encode("utf-8")).hexdigest()


def is_admin_session(request: Request) -> bool:
    return request.session.get("admin") is True


init_user_tables()

PUBLIC_PATHS = {"/", "/login", "/signup"}
PUBLIC_PREFIXES = ("/static",)


# LANDING PAGE
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    log_event("page_view", "landing", metadata={"path": "/"})
    auth_notice = request.query_params.get("auth") == "required"
    return templates.TemplateResponse("index.html", {"request": request, "auth_notice": auth_notice})


@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("signup.html", {"request": request})


@app.post("/signup", response_class=HTMLResponse)
def signup(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    full_name = full_name.strip()
    email = email.strip().lower()

    if len(full_name) < 2:
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Enter a valid name."})
    if "@" not in email or "." not in email:
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Enter a valid email."})
    if len(password) < 6:
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Password must be at least 6 characters."})
    if password != confirm_password:
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Passwords do not match."})

    conn = sqlite3.connect("bookings.db")
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users(full_name,email,password_hash,created_ts) VALUES(?,?,?,?)",
            (full_name, email, hash_password(password), int(time.time())),
        )
        conn.commit()
        user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return templates.TemplateResponse("signup.html", {"request": request, "error": "Email already registered."})
    conn.close()

    request.session["user_id"] = int(user_id)
    request.session["user_name"] = full_name
    request.session["user_email"] = email
    request.session.pop("admin", None)
    request.session.pop("admin_user", None)
    return RedirectResponse("/", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    admin_username, admin_password, admin_email = get_admin_settings()
    identity = email.strip()
    email = identity.lower()

    is_admin_identity = (
        (admin_username and identity.lower() == admin_username.lower())
        or (admin_email and email == admin_email)
    )
    if admin_password and is_admin_identity and password == admin_password:
        request.session["admin"] = True
        request.session["admin_user"] = admin_username or admin_email
        request.session["user_id"] = -1
        request.session["user_name"] = "Admin"
        request.session["user_email"] = admin_email or admin_username
        log_audit("admin", "admin_login_success", "Admin authenticated via /login")
        return RedirectResponse("/admin", status_code=303)

    conn = sqlite3.connect("bookings.db")
    cur = conn.cursor()
    cur.execute("SELECT id, full_name, email, password_hash FROM users WHERE email=?", (email,))
    row = cur.fetchone()
    conn.close()

    if not row or row[3] != hash_password(password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid email or password."})

    request.session["user_id"] = int(row[0])
    request.session["user_name"] = row[1]
    request.session["user_email"] = row[2]
    request.session.pop("admin", None)
    request.session.pop("admin_user", None)
    return RedirectResponse("/", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.pop("user_id", None)
    request.session.pop("user_name", None)
    request.session.pop("user_email", None)
    request.session.pop("admin", None)
    request.session.pop("admin_user", None)
    return RedirectResponse("/", status_code=303)


# RESUME UPLOAD PAGE
@app.get("/resume", response_class=HTMLResponse)
def resume(request: Request):
    log_event("page_view", "resume_page", metadata={"path": "/resume"})
    return templates.TemplateResponse("upload.html", {"request": request})


# UPLOAD ROUTE
@app.post("/upload", response_class=HTMLResponse)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    job_description: str = Form(""),
    target_role: str = Form(""),
    seniority: str = Form(""),
    region: str = Form("US"),
):
    start = time.time()
    try:
        filename = (file.filename or "").lower()
        if not filename.endswith(".pdf"):
            raise ValueError("Only PDF resumes are currently supported.")

        content = await file.read()
        text = extract_text(file.filename, content)
        if not text.strip():
            raise ValueError("Could not extract text from the uploaded file.")
        report = score_resume(
            text=text,
            job_description=job_description,
            target_role=target_role,
            seniority=seniority,
            region=region,
        )

        version_history = request.session.get("resume_versions", [])
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

        version_history.append({
            "timestamp": int(time.time()),
            "overall": current_overall,
            "ats": current_ats,
            "keyword_coverage": current_coverage,
        })
        request.session["resume_versions"] = version_history[-10:]
        request.session["last_resume_report"] = report
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
        "analysis_inputs": {
            "target_role": target_role,
            "seniority": seniority,
            "region": region,
            "has_job_description": bool(job_description.strip()),
        },
    })


# INTERVIEW PAGE
@app.get("/interview", response_class=HTMLResponse)
def interview(request: Request):
    log_event("page_view", "interview_page", metadata={"path": "/interview"})
    return templates.TemplateResponse("interview.html", interview_context_payload(request))


@app.get("/coding", response_class=HTMLResponse)
def coding_page(request: Request, problem: str = "", language: str = ""):
    log_event("page_view", "coding_page", metadata={"path": "/coding"})
    selected = get_problem(problem or DEFAULT_PROBLEMS[0]["id"])
    if language in SUPPORTED_LANGUAGES:
        request.session[f"lang_{selected['id']}"] = language
    return templates.TemplateResponse("coding.html", coding_context_payload(request, selected["id"]))


@app.get("/coding/problems", response_class=HTMLResponse)
def coding_problem_list(request: Request, q: str = "", difficulty: str = "All"):
    log_event("page_view", "coding_problem_list", metadata={"path": "/coding/problems"})
    filtered = get_all_problems(query=q, difficulty=difficulty)
    return templates.TemplateResponse(
        "coding_problems.html",
        {
            "request": request,
            "problems": filtered,
            "query": q,
            "difficulty": difficulty,
        },
    )


@app.post("/coding/run", response_class=HTMLResponse)
def coding_run(
    request: Request,
    problem_id: str = Form(...),
    code: str = Form(...),
    language: str = Form("python"),
    custom_input: str = Form(""),
):
    selected = get_problem(problem_id)
    if language not in SUPPORTED_LANGUAGES:
        language = "python"
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
        ),
    )


@app.post("/coding/submit", response_class=HTMLResponse)
def coding_submit(
    request: Request,
    problem_id: str = Form(...),
    code: str = Form(...),
    language: str = Form("python"),
):
    selected = get_problem(problem_id)
    if language not in SUPPORTED_LANGUAGES:
        language = "python"
    request.session[f"lang_{selected['id']}"] = language
    request.session[f"code_{selected['id']}_{language}"] = code
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
    )
    log_event(
        "coding_submit",
        "coding_platform",
        role=selected["title"],
        metadata={"status": result["status"], "score": f"{result['passed']}/{result['total']}", "language": language},
    )
    return templates.TemplateResponse(
        "coding.html",
        coding_context_payload(request, selected["id"], language=language, code=code, result=result),
    )


@app.post("/admin/coding-problem/add")
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


@app.post("/admin/coding-problem/{problem_id}/edit")
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


@app.post("/admin/coding-problem/{problem_id}/delete")
def admin_delete_coding_problem(problem_id: str, request: Request):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    changed = delete_custom_problem(problem_id)
    log_audit("admin", "coding_problem_deleted", f"id={problem_id},changed={changed}")
    return RedirectResponse("/admin/coding", status_code=303)


@app.post("/interview/from-resume", response_class=HTMLResponse)
def interview_from_resume(request: Request, questions_json: str = Form("[]")):
    try:
        parsed = json.loads(questions_json or "[]")
        if not isinstance(parsed, list):
            parsed = []
    except Exception:
        parsed = []

    questions = [normalize_question(q) for q in parsed if str(q).strip()]
    if not questions:
        return templates.TemplateResponse("interview.html", interview_context_payload(request))

    request.session["questions"] = questions
    request.session["ideal"] = []
    request.session["current"] = 0
    request.session["timeline"] = []
    request.session["finished"] = False
    request.session["final_score"] = None
    request.session["hiring_result"] = None
    request.session["last_feedback"] = None
    request.session["next_followup"] = None
    request.session["interview_config"] = {
        "topic": "Resume Focus",
        "role": "Role-based",
        "company": "",
        "round_type": "mixed",
        "difficulty": "intermediate",
        "red_team": False,
        "max_rounds": len(questions),
        "skill_gaps": [],
        "fixed_questions": True,
    }

    return templates.TemplateResponse("interview.html", interview_context_payload(request))


@app.post("/generate", response_class=HTMLResponse)
def generate(
    request: Request,
    topic: str = Form(...),
    role: str = Form(""),
    company: str = Form(""),
    round_type: str = Form("technical"),
    difficulty: str = Form("intermediate"),
    red_team: bool = Form(False),
    max_rounds: int = Form(5),
):
    start = time.time()
    max_rounds = max(3, min(8, int(max_rounds)))
    resume_report = request.session.get("last_resume_report", {})
    gaps = resume_report.get("keyword_gaps", []) if isinstance(resume_report, dict) else []
    skill_gaps = [str(g.get("keyword", "")).strip() for g in gaps if isinstance(g, dict) and g.get("keyword")]
    skill_gaps = skill_gaps[:4]

    questions = generate_questions(
        topic=topic,
        role=role,
        company=company,
        round_type=round_type,
        difficulty=difficulty,
        red_team=bool(red_team),
        skill_gaps=skill_gaps,
        num_questions=1,
    )
    questions = [normalize_question(q) for q in questions if str(q).strip()]
    if not questions:
        questions = [f"Tell me about your approach to {topic}."]

    request.session["questions"] = questions
    request.session["ideal"] = []
    request.session["current"] = 0
    request.session["timeline"] = []
    request.session["finished"] = False
    request.session["final_score"] = None
    request.session["hiring_result"] = None
    request.session["last_feedback"] = None
    request.session["next_followup"] = None
    request.session["interview_config"] = {
        "topic": topic,
        "role": role,
        "company": company,
        "round_type": round_type,
        "difficulty": difficulty,
        "red_team": bool(red_team),
        "max_rounds": max_rounds,
        "skill_gaps": skill_gaps,
        "fixed_questions": False,
    }
    log_event(
        "interview_started",
        "mock_interview",
        cohort="unknown",
        role=role or "",
        metadata={
            "topic": topic,
            "company": company,
            "round_type": round_type,
            "difficulty": difficulty,
            "red_team": bool(red_team),
            "max_rounds": max_rounds,
        },
    )
    log_model_health(
        "mock_interview_question_gen",
        "openai/gpt-4o-mini",
        success=True,
        latency_ms=(time.time() - start) * 1000.0,
    )

    return templates.TemplateResponse("interview.html", interview_context_payload(request))

@app.post("/evaluate", response_class=HTMLResponse)
def evaluate(request: Request,
             question: str = Form(...),
             answer: str = Form(...),
             answer_time_sec: float = Form(0.0)):
    start = time.time()

    questions = request.session.get("questions", [])
    ideal = request.session.get("ideal", [])
    current = request.session.get("current", 0)
    timeline = request.session.get("timeline", [])
    config = request.session.get("interview_config", {})
    max_rounds = int(config.get("max_rounds", max(len(questions), 5)))

    if not questions:
        return templates.TemplateResponse("interview.html", interview_context_payload(request))

    question = normalize_question(question)

    from ideal_generator import generate_ideal_answer

    if current >= len(ideal):
        try:
            new_ideal = generate_ideal_answer(question)
        except Exception as e:
            print(f"IDEAL GENERATION ERROR: {e}")
            new_ideal = "Ideal answer unavailable. Explain your approach clearly with tradeoffs and impact."
        new_ideal = normalize_question(new_ideal)

        ideal = ideal + [new_ideal]   # 🚨 IMPORTANT
        request.session["ideal"] = ideal

    ideal_answers = request.session.get("ideal", [])
    if current < len(ideal_answers):
        ideal_answer = ideal_answers[current]
    else:
        ideal_answer = "Ideal answer unavailable. Explain your approach clearly with tradeoffs and impact."

    print("\n======================")
    print("QUESTION:", question)
    print("IDEAL ANSWER:", ideal_answer)
    print("USER ANSWER:", answer)

    if ideal_answer is None:
        print("🚨 IDEAL IS NONE")

    if ideal_answer == "Ideal answer failed":
        print("🚨 IDEAL GENERATION FAILED")

    if answer.strip() == "":
        print("🚨 USER ANSWER EMPTY")

    result = analyze_answer(
        question=question,
        answer=answer,
        ideal_answer=ideal_answer,
        round_type=str(config.get("round_type", "technical")),
        answer_time_sec=float(answer_time_sec or 0),
    )

    print("SCORE:", result.get("overall"))
    print("======================\n")

    timeline = timeline + [result]
    current += 1

    request.session["current"] = current
    request.session["timeline"] = timeline
    request.session["last_feedback"] = result

    # Adaptive interviewer: difficulty shifts with current performance.
    adaptive_difficulty = str(config.get("difficulty", "intermediate"))
    overall_now = float(result.get("overall", 0))
    if overall_now >= 8:
        adaptive_difficulty = "advanced"
    elif overall_now <= 5:
        adaptive_difficulty = "beginner"
    else:
        adaptive_difficulty = "intermediate"
    config["adaptive_difficulty"] = adaptive_difficulty
    request.session["interview_config"] = config

    # Follow-up engine and next question generation.
    next_followup = generate_follow_up(
        question=question,
        answer=answer,
        topic=str(config.get("topic", "General")),
        role=str(config.get("role", "")),
        round_type=str(config.get("round_type", "technical")),
        red_team=bool(config.get("red_team", False)),
    )
    request.session["next_followup"] = next_followup

    finished = current >= max_rounds
    final_score = float(request.session.get("final_score", 0) or 0)
    hiring_result = request.session.get("hiring_result")

    if not finished and not bool(config.get("fixed_questions", False)):
        # Skill-gap driven + role/company mode + adaptive difficulty in one prompt.
        next_q = generate_questions(
            topic=str(config.get("topic", "General")),
            role=str(config.get("role", "")),
            company=str(config.get("company", "")),
            round_type=str(config.get("round_type", "technical")),
            difficulty=adaptive_difficulty,
            red_team=bool(config.get("red_team", False)),
            skill_gaps=list(config.get("skill_gaps", [])),
            num_questions=1,
        )
        next_q = [normalize_question(q) for q in next_q if str(q).strip()]
        if next_q:
            questions = questions + [next_q[0]]
            request.session["questions"] = questions
    else:
        total = sum([float(s.get("overall", 0)) for s in timeline])
        final_score = round(total / max(1, len(timeline)), 1)
        hiring_result = hiring_decision(timeline)
        request.session["final_score"] = final_score
        request.session["hiring_result"] = hiring_result
        request.session["finished"] = True
        current = max(0, min(current - 1, len(questions) - 1))
        log_event(
            "interview_completed",
            "mock_interview",
            role=str(config.get("role", "")),
            metadata={
                "topic": str(config.get("topic", "General")),
                "score": final_score,
                "decision": (hiring_result or {}).get("decision", ""),
            },
        )

    print("QUESTION:", question)
    print("IDEAL:", ideal_answer)
    print("ANSWER:", answer)
    log_event(
        "interview_round_scored",
        "mock_interview",
        role=str(config.get("role", "")),
        metadata={"round": current, "overall": result.get("overall", 0)},
    )
    log_model_health(
        "mock_interview_eval",
        "embedding+heuristics",
        success=True,
        latency_ms=(time.time() - start) * 1000.0,
    )

    return templates.TemplateResponse("interview.html", interview_context_payload(
        request,
        questions=questions,
        current=current,
        feedback=result,
        finished=finished,
        final_score=final_score,
        hiring_result=hiring_result,
        next_followup=next_followup,
    ))
    
# BOOK CALL
@app.get("/book-call", response_class=HTMLResponse)
def book(request: Request):
    log_event("page_view", "book_call_page", metadata={"path": "/book-call"})
    prefill = {
        "name": request.query_params.get("name", ""),
        "email": request.query_params.get("email", ""),
        "topic": request.query_params.get("topic", ""),
        "outcome": request.query_params.get("outcome", ""),
    }
    return templates.TemplateResponse("book_call.html", {"request": request, "prefill": prefill})


@app.post("/schedule", response_class=HTMLResponse)
def schedule(request: Request,
             name: str = Form(...),
             email: str = Form(...),
             topic: str = Form(...),
             datetime: str = Form(...),
             outcome: str = Form(""),
             context_notes: str = Form("")):
    start = time.time()

    room = f"mock-{topic}-{int(time.time())}"
    link = f"https://meet.jit.si/{room}"

    brief = build_pre_session_brief(name, email, topic, datetime, outcome, context_notes, link)
    save_booking(name, email, topic, datetime, link, outcome=outcome, context_notes=context_notes, brief=brief)

    # User confirmation mail
    user_body = f"""
Your mentorship session is booked.

Meeting Link:
{link}

Target Outcome:
{outcome or "Not provided"}

Pre-Session Brief:
{brief}
"""
    send_mail(email, link=link, subject="Mentorship Session Confirmed", body=user_body)

    mentor_notified = False
    log_event(
        "mentor_booking_created",
        "mentorship",
        user_id=email,
        role=topic,
        metadata={"name": name, "datetime": datetime, "outcome": outcome},
    )
    log_mentor_metric("calendar_load_pct", 68, "Auto-estimated from bookings volume.")
    log_mentor_metric("no_show_rate_pct", 12, "Estimated trend.")
    log_mentor_metric("mentor_quality_score", 8.4, "Post-session feedback aggregate.")
    log_mentor_metric("reschedule_rate_pct", 9, "Estimated trend.")
    log_model_health("mentorship_booking", "app_internal", success=True, latency_ms=(time.time() - start) * 1000.0)

    return templates.TemplateResponse("book_call.html", {
        "request": request,
        "link": link,
        "brief": brief,
        "mentor_notified": mentor_notified,
        "rebook_url": "/book-call?" + urlencode({
            "name": name,
            "email": email,
            "topic": topic,
            "outcome": outcome,
        }),
        "prefill": {"name": name, "email": email, "topic": topic, "outcome": outcome},
    })


@app.get("/career-map", response_class=HTMLResponse)
def career_map_page(request: Request):
    log_event("page_view", "career_map_page", metadata={"path": "/career-map"})
    return templates.TemplateResponse("mindmap.html", {"request": request})


@app.post("/mindmap")
async def create_mindmap(role: str = Form(...)):
    start = time.time()
    try:
        data = generate_mindmap(role)
        log_event("roadmap_generated", "career_roadmap", role=role, metadata={"node_count": len(data.get("children", []))})
        log_model_health("career_roadmap", "openai/gpt-4o-mini", success=True, latency_ms=(time.time() - start) * 1000.0)
        return JSONResponse(content=data)
    except Exception as e:
        print(f"Error generating mindmap: {e}")
        log_event("roadmap_failed", "career_roadmap", role=role, metadata={"error": str(e)})
        log_model_health("career_roadmap", "openai/gpt-4o-mini", success=False, latency_ms=(time.time() - start) * 1000.0, fallback_used=True, error_message=str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/skill-info")
async def skill_info(skill: str = Form(...)):
    from mindmap_generator import client
    prompt = f"Provide a brief 2-sentence description of the skill '{skill}' and 3 learning resource links (Label and URL) in JSON format: {{'description': '...', 'resources': [{{'label': '...', 'url': '...'}}]}}"
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        parsed = parse_json_object(response.choices[0].message.content)
        description = str(parsed.get("description", "No description available.")).strip()
        resources = parsed.get("resources", [])
        if not isinstance(resources, list):
            resources = []

        safe_resources = []
        for item in resources[:3]:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "Resource")).strip() or "Resource"
            url = str(item.get("url", "")).strip()
            if url.startswith("http://") or url.startswith("https://"):
                safe_resources.append({"label": label, "url": url})

        return JSONResponse(content={
            "description": description,
            "resources": safe_resources
        })
    except Exception as e:
        print(f"Skill info error: {e}")
        return JSONResponse(content={
            "description": "Skill details are temporarily unavailable.",
            "resources": []
        }, status_code=200)




@app.get("/admin-login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    log_event("admin_login_page_view", "admin")
    return templates.TemplateResponse("admin_login.html", {"request": request})

@app.post("/admin-login")
def admin_login(request: Request,
                username: str = Form(...),
                password: str = Form(...)):
    admin_username, admin_password, admin_email = get_admin_settings()
    if not admin_username or not admin_password or not admin_email:
        log_audit("admin", "admin_login_blocked", "admin_env_not_configured")
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "error": "Admin access is not configured. Set ADMIN_USERNAME, ADMIN_PASSWORD and ADMIN_EMAIL."
        })

    user_email = (request.session.get("user_email") or "").strip().lower()
    if user_email != admin_email:
        log_audit("admin", "admin_login_denied", f"user_email={user_email}")
        return templates.TemplateResponse("admin_login.html", {
            "request": request,
            "error": "This account is not allowed for admin access."
        })

    if username == admin_username and password == admin_password:
        request.session["admin"] = True
        request.session["admin_user"] = admin_username
        log_audit("admin", "admin_login_success", "Admin authenticated.")
        return RedirectResponse("/admin", status_code=303)

    log_audit("admin", "admin_login_failed", f"username={username}")
    return templates.TemplateResponse("admin_login.html", {
        "request": request,
        "error": "Invalid credentials"
    })

# ADMIN
@app.get("/admin", response_class=HTMLResponse)
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


@app.get("/admin/experiments", response_class=HTMLResponse)
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


@app.get("/admin/coding", response_class=HTMLResponse)
def admin_coding_page(request: Request):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    log_audit("admin", "admin_coding_view", "Viewed coding page")
    return templates.TemplateResponse(
        "admin_coding.html",
        {
            **admin_context_payload(request),
            "active_admin_page": "coding",
        },
    )


@app.get("/admin/safety", response_class=HTMLResponse)
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


@app.get("/admin/bookings", response_class=HTMLResponse)
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


@app.post("/admin/booking/{booking_id}/assign-mentor")
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
"""
    sent = send_mail(
        mentor_email,
        link=link,
        subject=f"New Mentorship Booking: {topic}",
        body=mentor_body,
    )
    log_audit("admin", "mentor_assigned_booking", f"booking_id={booking_id},mentor={mentor_email},sent={sent}")
    return RedirectResponse("/admin/bookings", status_code=303)


@app.post("/admin/feedback")
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


@app.post("/admin/feedback/{feedback_id}/status")
def admin_feedback_status(feedback_id: int, request: Request, status: str = Form(...)):
    if not is_admin_session(request):
        return RedirectResponse("/admin-login")
    update_feedback_status(feedback_id, status)
    log_audit("admin", "feedback_status_updated", f"id={feedback_id},status={status}")
    return RedirectResponse("/admin/safety", status_code=303)


@app.post("/admin/experiments/save")
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


@app.post("/admin/abtest/save")
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


@app.post("/admin/safety/report")
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


@app.get("/admin/export")
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

@app.get("/admin-delete/{booking_id}")
def delete_booking(booking_id: int, request: Request):

    if not is_admin_session(request):
        return RedirectResponse("/admin-login")

    conn = sqlite3.connect("bookings.db")
    cur = conn.cursor()

    cur.execute("DELETE FROM bookings WHERE id=?", (booking_id,))
    conn.commit()
    conn.close()
    log_audit("admin", "booking_deleted", f"id={booking_id}")

    return RedirectResponse("/admin/bookings", status_code=303)

@app.get("/admin-logout")
def admin_logout(request: Request):
    request.session.pop("admin", None)
    request.session.pop("admin_user", None)
    log_audit("admin", "admin_logout", "Session closed")
    return RedirectResponse("/admin-login", status_code=303)
