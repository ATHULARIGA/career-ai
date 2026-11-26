import json
import re
import time
import uuid
from typing import Any

import requests
from bs4 import BeautifulSoup
from fastapi import Request

import db.backend as db
from core.config import (
    CODING_DEEP_INSIGHTS,
    logger,
)
from core.database import get_user_memory
from core.security import current_user_plan
from services.analytics.admin_analytics import dashboard_payload
from services.booking.booking_db import get_bookings
from services.coding.coding_platform import (
    DEFAULT_PROBLEMS,
    SUPPORTED_LANGUAGES,
    contest_snapshot,
    coverage_report,
    daily_goal_progress,
    get_all_problems,
    get_custom_problems,
    get_problem_timeline,
    get_submission_stats_extended,
    get_user_submission_summary,
    interview_readiness_score,
    parse_test_lines,
    personalized_practice_queue,
    recommend_next_problem,
    starter_for_language,
    study_plan,
    topic_mastery_report,
    weak_tags_for_user,
)


def _is_safe_public_url(url: str) -> tuple[bool, str]:
    """Validates that a URL uses http/https and resolves only to public IP addresses (anti-SSRF)."""
    import ipaddress
    import socket
    from urllib.parse import urlparse

    try:
        parsed = urlparse((url or "").strip())
    except Exception:
        return False, "Invalid URL format."
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False, "Only http and https URLs are supported."
    host = parsed.hostname.strip().lower()
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or host.endswith(".local") or host.endswith(".internal"):
        return False, "Blocked internal or loopback host."
    try:
        addr_infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except Exception:
        return False, "Could not resolve target hostname."
    for info in addr_infos:
        ip_str = info[4][0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_unspecified:
                return False, "Blocked non-public IP address."
        except ValueError:
            return False, "Invalid resolved IP address."
    return True, ""


def normalize_role_title(raw_role: str) -> str:
    """Normalizes role titles and removes accidental duplicated role suffixes."""
    cleaned = (raw_role or "").strip()
    if not cleaned:
        return ""
    return re.sub(r"(Developer|Engineer|Architect|Designer|Manager)\1+", r"\1", cleaned, flags=re.IGNORECASE)


def scrape_job_link(url: str) -> dict:
    if not url:
        return {"text": "", "error": "No URL provided."}

    # 1. SSRF guard: allow only public http(s) destinations
    is_safe, err_msg = _is_safe_public_url(url)
    if not is_safe:
        return {"text": "", "error": err_msg}

    # 2. Block List for Unsupported Login-Wall domains
    UNSUPPORTED_DOMAINS = ["linkedin.com", "indeed.com", "glassdoor.com"]
    if any(d in url.lower() for d in UNSUPPORTED_DOMAINS):
        return {"text": "", "error": "LinkedIn/Indeed/Glassdoor require login — please paste the JD text directly."}
        
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        }
        # 3. Hard timeout ceiling (8s) and disable blind redirects to internal hosts
        response = requests.get(url, headers=headers, timeout=8, allow_redirects=False)
        if getattr(response, "is_redirect", False) or getattr(response, "is_permanent_redirect", False):
            loc = response.headers.get("location", "")
            ok_redir, redir_err = _is_safe_public_url(loc)
            if not ok_redir:
                return {"text": "", "error": redir_err or "Blocked unsafe redirect."}
            response = requests.get(loc, headers=headers, timeout=8, allow_redirects=False)
        
        if response.status_code >= 400:
            return {"text": "", "error": f"Could not access URL (Status {response.status_code})."}
            
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 3. Specialized Selectors
        content_node = None
        if "greenhouse.io" in url.lower():
            content_node = soup.select_one(".job-body, #content, #main")
        elif "lever.co" in url.lower():
            content_node = soup.select_one(".section-wrapper, .content, .job-info")
            
        if content_node:
            soup = content_node
            
        for script_or_style in soup(["script", "style", "noscript", "header", "footer", "nav", "iframe"]):
            script_or_style.decompose()
            
        text = soup.get_text(separator="\n")
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)
        
        # 4. Length Thresholds Checks
        if len(text.strip()) < 120:
            return {"text": "", "error": "Could not extract a readable description — try pasting the text manually instead."}
            
        # Limit scraped context to 15k chars to prevent prompt blowouts
        return {"text": text[:15000], "error": None}
    except requests.Timeout:
        return {"text": "", "error": "Request timed out (8s limit). Page took too long to load."}
    except Exception as e:
        logger.warning("Scraping failed for %s: %s", url, e)
        return {"text": "", "error": f"Scraping failed: {e!s}"}


def normalize_question(q):
    if isinstance(q, dict):
        q = q.get("question", "")
    q = str(q)
    q = q.replace("\n", " ")
    q = q.replace("Question:", "")
    q = q.strip()
    return q


INTERVIEW_QUESTION_BANK = {
    "python": [
        "How would you optimize a Python API endpoint that becomes CPU-bound under peak load?",
        "Explain the difference between threading, multiprocessing, and asyncio with one production use case each.",
        "How do you design robust retry logic for external API calls in Python services?",
    ],
    "sql": [
        "How do you debug a slow query in production and validate index strategy changes safely?",
        "Explain window functions with a practical example from analytics reporting.",
        "How would you detect and remove duplicate records without data loss?",
    ],
    "react": [
        "How would you prevent unnecessary re-renders in a React page with multiple data widgets?",
        "Explain how you structure state management for a medium-size product dashboard.",
        "How do you debug hydration mismatch issues in server-rendered React apps?",
    ],
    "system design": [
        "Design a rate-limited URL shortener that supports analytics and high write throughput.",
        "How would you scale a notification system for multi-channel delivery?",
        "Design a logging pipeline with low-latency search and retention controls.",
    ],
    "behavioral": [
        "Tell me about a time you disagreed with a technical direction and how you resolved it.",
        "Describe a high-pressure incident you handled and what you changed afterwards.",
        "Give an example of mentoring someone and measuring the outcome.",
    ],
}


def bank_questions(topic: str, role: str = "", round_type: str = "", limit: int = 2) -> list[str]:
    key = (topic or round_type or "behavioral").strip().lower()
    pool = INTERVIEW_QUESTION_BANK.get(key, INTERVIEW_QUESTION_BANK.get("behavioral", []))
    role = role.strip()
    seeded = []
    for q in pool[: max(1, limit)]:
        if role:
            seeded.append(f"For a {role} role: {q}")
        else:
            seeded.append(q)
    return seeded[:limit]


def interview_metrics(timeline: list) -> dict:
    if not timeline:
        return {"avg_score": 0.0, "avg_wpm": 0, "avg_filler_pct": 0.0}
    scores = [float(t.get("overall", 0) or 0) for t in timeline if isinstance(t, dict)]
    wpms = [int((t.get("voice_pace", {}) or {}).get("wpm", 0) or 0) for t in timeline if isinstance(t, dict)]
    fillers = [float((t.get("voice_pace", {}) or {}).get("filler_density_pct", 0) or 0) for t in timeline if isinstance(t, dict)]
    return {
        "avg_score": round(sum(scores) / max(1, len(scores)), 1),
        "avg_wpm": int(round(sum(wpms) / max(1, len(wpms)))) if wpms else 0,
        "avg_filler_pct": round(sum(fillers) / max(1, len(fillers)), 1) if fillers else 0.0,
    }


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


def get_selectable_resumes_for_user(user_email: str, request: Request = None) -> list:
    """Returns saved resumes or uploaded resume for selection (no report review runs)."""
    email = (user_email or "").strip().lower()
    items = []
    seen_ids = set()

    from core.database import (
        get_saved_resume_by_id,
        get_user_saved_resumes,
        seed_default_sample_resume,
    )

    # 1. Any resume uploaded in the active session
    if request:
        uploaded = request.session.get("interview_uploaded_resume")
        if uploaded and isinstance(uploaded, dict) and uploaded.get("id"):
            u_id = uploaded["id"]
            if u_id not in seen_ids:
                seen_ids.add(u_id)
                items.append({
                    "id": u_id,
                    "title": f"{uploaded.get('title') or 'Uploaded Resume'} ({uploaded.get('target_role') or 'Engineer'})",
                    "target_role": uploaded.get("target_role") or "Software Engineer",
                    "source": "uploaded",
                    "raw_id": 0,
                })

    # 2. Saved resumes for authenticated user
    if email:
        saved = get_user_saved_resumes(email)
        for s in saved:
            s_id = f"saved_{s['id']}"
            if s_id not in seen_ids:
                seen_ids.add(s_id)
                items.append({
                    "id": s_id,
                    "title": f"{s.get('title') or 'Saved Resume'} ({s.get('target_role') or 'Engineer'})",
                    "target_role": s.get("target_role") or "",
                    "source": "saved",
                    "raw_id": s["id"],
                })

    # 3. If no saved resumes exist, provide the default sample saved resume
    if not items:
        sample_id = seed_default_sample_resume()
        sample_resume = get_saved_resume_by_id(sample_id, email)
        if sample_resume:
            items.append({
                "id": f"saved_{sample_id}",
                "title": f"{sample_resume.get('title') or 'Athul Ariga - Data Engineer & Python Developer (LaTeX)'} ({sample_resume.get('target_role') or 'Data Engineer'})",
                "target_role": sample_resume.get("target_role") or "Data Engineer & Python Developer",
                "source": "saved",
                "raw_id": sample_id,
            })
        else:
            items.append({
                "id": "saved_1",
                "title": "Athul Ariga - Data Engineer & Python Developer (LaTeX)",
                "target_role": "Data Engineer & Python Developer",
                "source": "saved",
                "raw_id": 1,
            })

    return items


def resolve_resume_context(selected_id: str, user_email: str, request: Request = None) -> tuple:
    """Resolves resume data, text, and target role for a given selected resume id."""
    email = (user_email or "").strip().lower()
    sel = (selected_id or "").strip()

    from core.database import (
        get_saved_resume_by_id,
    )

    report = None
    resume_text = ""
    target_role = ""

    # Check session uploaded resume
    if request:
        uploaded = request.session.get("interview_uploaded_resume")
        if uploaded and isinstance(uploaded, dict):
            if not sel or sel == uploaded.get("id") or sel.startswith("uploaded_"):
                resume_text = uploaded.get("text", "")
                target_role = uploaded.get("target_role", "")
                report = {"resume_text": resume_text, "target_role": target_role}
                return report, resume_text, target_role or "Software Engineer"

    if sel.startswith("saved_"):
        try:
            raw_id = int(sel.replace("saved_", ""))
            saved = get_saved_resume_by_id(raw_id, email)
            if saved:
                resume_text = saved.get("raw_content", "")
                target_role = saved.get("target_role", "")
                report = {"resume_text": resume_text, "target_role": target_role}
        except Exception:
            pass

    if not resume_text:
        from core.database import DEFAULT_ATHUL_RESUME, seed_default_sample_resume
        try:
            sample_id = seed_default_sample_resume()
            saved = get_saved_resume_by_id(sample_id, email)
            if saved:
                resume_text = saved.get("raw_content", "")
                target_role = saved.get("target_role", "")
                report = {"resume_text": resume_text, "target_role": target_role}
        except Exception:
            resume_text = DEFAULT_ATHUL_RESUME
            target_role = "Data Engineer & Python Developer"
            report = {"resume_text": resume_text, "target_role": target_role}

    if not target_role and request:
        target_role = (request.session.get("interview_config", {}) or {}).get("role", "")

    if not target_role:
        target_role = "Software Engineer"

    return report or {}, resume_text, target_role


def interview_context_payload(request: Request, **extra):
    timeline = request.session.get("timeline", [])
    user_email = (request.session.get("user_email") or "").strip().lower()
    memory = get_user_memory(user_email)
    config = request.session.get("interview_config", {}) or {}

    from core.database import get_user_cheatsheets
    from services.interview.cheatsheet_generator import (
        extract_technologies_from_resume,
        get_cheatsheet_for_technology,
    )

    selectable_resumes = get_selectable_resumes_for_user(user_email, request)
    available_ids = [r["id"] for r in selectable_resumes]

    selected_resume_id = request.session.get("selected_resume_id", "")
    if selected_resume_id not in available_ids:
        selected_resume_id = available_ids[0] if available_ids else "latest"
    request.session["selected_resume_id"] = selected_resume_id

    resume_report, resume_text, target_role = resolve_resume_context(selected_resume_id, user_email, request)

    default_setup = {
        "topic": memory.get("focus_area", "") or "Python",
        "role": target_role or memory.get("target_role", ""),
        "company": memory.get("target_company", ""),
    }

    resume_techs = extract_technologies_from_resume(resume_text, resume_report)
    saved_custom = get_user_cheatsheets(user_email) if user_email else request.session.get("session_custom_cheatsheets", [])
    custom_tech_names = [c["tech_name"] for c in saved_custom if isinstance(c, dict) and c.get("tech_name")]

    initial_tech = resume_techs[0] if resume_techs else "FastAPI"
    initial_cheatsheet = get_cheatsheet_for_technology(initial_tech, resume_text=resume_text, target_role=target_role)

    revised_map = {c["tech_name"]: c.get("revised_indices", []) for c in saved_custom if isinstance(c, dict)}
    if initial_tech in revised_map:
        initial_cheatsheet["revised_indices"] = revised_map[initial_tech]
    else:
        initial_cheatsheet["revised_indices"] = request.session.get(f"revised_{initial_tech.lower()}", [])

    payload = {
        "request": request,
        "questions": request.session.get("questions", []),
        "current": request.session.get("current", 0),
        "finished": request.session.get("finished", False),
        "config": config,
        "default_setup": default_setup,
        "timeline": timeline,
        "feedback": request.session.get("last_feedback"),
        "final_score": request.session.get("final_score"),
        "hiring_result": request.session.get("hiring_result"),
        "next_followup": request.session.get("next_followup"),
        "session_metrics": interview_metrics(timeline),
        "user_plan": current_user_plan(request),
        "resume_technologies": resume_techs,
        "custom_technologies": custom_tech_names,
        "active_technology": initial_tech,
        "initial_cheatsheet": initial_cheatsheet,
        "has_resume": bool(resume_text),
        "target_role": target_role,
        "selectable_resumes": selectable_resumes,
        "selected_resume_id": selected_resume_id,
    }
    payload.update(extra)
    return payload


_TIMED_ALLOWED = {"35", "45"}


def _timed_session_key(problem_id: str) -> str:
    return f"timed_mode_{str(problem_id or '').strip()}"


def _clear_timed_mode(request: Request, problem_id: str) -> None:
    request.session.pop(_timed_session_key(problem_id), None)


def _apply_timed_mode_selection(request: Request, problem_id: str, timed_mode: str) -> dict[str, Any]:
    mode = str(timed_mode or "").strip()
    key = _timed_session_key(problem_id)
    now = int(time.time())
    if mode in _TIMED_ALLOWED:
        state = request.session.get(key) or {}
        if str(state.get("duration_min") or "") != mode:
            state = {
                "duration_min": int(mode),
                "start_ts": now,
                "submitted": False,
                "job_id": "",
            }
            request.session[key] = state
    elif mode == "":
        _clear_timed_mode(request, problem_id)
    return _timed_mode_state(request, problem_id)


def _timed_mode_state(request: Request, problem_id: str) -> dict[str, Any]:
    state = request.session.get(_timed_session_key(problem_id)) or {}
    if not state:
        return {
            "enabled": False,
            "duration_min": 0,
            "remaining_sec": 0,
            "elapsed_sec": 0,
            "expired": False,
            "submitted": False,
            "job_id": "",
        }
    duration = int(state.get("duration_min") or 0)
    start_ts = int(state.get("start_ts") or 0)
    now = int(time.time())
    elapsed = max(0, now - start_ts)
    total = max(0, duration * 60)
    remaining = max(0, total - elapsed)
    expired = remaining <= 0
    return {
        "enabled": duration > 0,
        "duration_min": duration,
        "remaining_sec": remaining,
        "elapsed_sec": elapsed,
        "expired": expired,
        "submitted": bool(state.get("submitted")),
        "job_id": str(state.get("job_id") or ""),
    }


def _mark_timed_mode_submitted(request: Request, problem_id: str, job_id: str = "") -> None:
    key = _timed_session_key(problem_id)
    state = request.session.get(key) or {}
    if not state:
        return
    state["submitted"] = True
    if job_id:
        state["job_id"] = job_id
    request.session[key] = state


def _solved_problem_count(user_email: str) -> int:
    email = (user_email or "").strip().lower()
    if not email:
        return 0
    try:
        conn = db.get_conn()
        cur = conn.cursor()
        db.execute(
            cur,
            """
            SELECT COUNT(DISTINCT problem_id)
            FROM coding_submissions
            WHERE user_email=? AND mode='submit' AND status='Accepted'
            """,
            (email,),
        )
        row = cur.fetchone() or (0,)
        conn.close()
        return int(row[0] or 0)
    except Exception:
        return 0


def _safe_call(fn, default, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        logger.warning("coding_safe_call_failed fn=%s err=%s", getattr(fn, "__name__", "unknown"), exc)
        return default


def _select_problem(problems, problem_id: str):
    pid = str(problem_id or "").strip()
    for p in problems:
        if str((p or {}).get("id") or "") == pid:
            return p
    if problems:
        return problems[0]
    return dict(DEFAULT_PROBLEMS[0])


def _readiness_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    total = int((summary or {}).get("total") or 0)
    accept = float((summary or {}).get("accept_rate") or 0.0)
    speed = float((summary or {}).get("avg_runtime_ms") or 0.0)
    consistency = min(100.0, total * 5.0)
    speed_score = 100.0 if speed <= 120 else max(20.0, 140.0 - (speed / 2.5))
    score = round((accept * 0.5) + (consistency * 0.25) + (speed_score * 0.25), 1)
    band = "High" if score >= 75 else ("Medium" if score >= 50 else "Low")
    return {
        "score": score,
        "band": band,
        "accept_rate": round(accept, 1),
        "consistency": round(consistency, 1),
        "speed_score": round(speed_score, 1),
    }


def _daily_goal_from_attempts(attempts: list, goal_accepted: int = 1, goal_review: int = 1) -> dict[str, Any]:
    now = int(time.time())
    today = time.strftime("%Y-%m-%d", time.localtime(now))
    bucket = {"accepted": 0, "review": 0}
    for a in attempts[:60]:
        ts = int(a.get("timestamp") or 0)
        if not ts:
            continue
        if time.strftime("%Y-%m-%d", time.localtime(ts)) != today:
            continue
        mode = str(a.get("mode") or "")
        status = str(a.get("status") or "")
        if mode == "submit" and status == "Accepted":
            bucket["accepted"] += 1
        if mode in ("run", "submit", "hint", "interviewer"):
            bucket["review"] += 1

    last_7 = []
    base = now - 6 * 24 * 60 * 60
    for i in range(7):
        day_ts = base + i * 24 * 60 * 60
        day = time.strftime("%Y-%m-%d", time.localtime(day_ts))
        accepted = 0
        review = 0
        for a in attempts[:100]:
            ts = int(a.get("timestamp") or 0)
            if not ts:
                continue
            if time.strftime("%Y-%m-%d", time.localtime(ts)) != day:
                continue
            mode = str(a.get("mode") or "")
            status = str(a.get("status") or "")
            if mode == "submit" and status == "Accepted":
                accepted += 1
            if mode in ("run", "submit", "hint", "interviewer"):
                review += 1
        met = accepted >= goal_accepted and review >= goal_review
        last_7.append({"day": day[5:], "accepted": accepted, "review": review, "met": met})

    streak = 0
    for day in reversed(last_7):
        if day["met"]:
            streak += 1
        else:
            break
    return {
        "accepted_today": int(bucket["accepted"]),
        "review_today": int(bucket["review"]),
        "goal_accepted": int(goal_accepted),
        "goal_review": int(goal_review),
        "goal_met_today": bucket["accepted"] >= goal_accepted and bucket["review"] >= goal_review,
        "streak_days": int(streak),
        "last_7_days": last_7,
    }


def _recommended_from_problems(problems: list, selected_id: str, attempts: list) -> dict[str, Any]:
    solved = set(
        str(a.get("problem_id") or "")
        for a in attempts
        if str(a.get("mode") or "") == "submit" and str(a.get("status") or "") == "Accepted"
    )
    for p in problems:
        pid = str((p or {}).get("id") or "")
        if not pid or pid == selected_id:
            continue
        if pid not in solved:
            return p
    for p in problems:
        pid = str((p or {}).get("id") or "")
        if pid and pid != selected_id:
            return p
    return {}


def _practice_queue_from_problems(problems: list, selected_id: str, attempts: list, limit: int = 5) -> list:
    solved = set(
        str(a.get("problem_id") or "")
        for a in attempts
        if str(a.get("mode") or "") == "submit" and str(a.get("status") or "") == "Accepted"
    )
    queue = []
    for p in problems:
        pid = str((p or {}).get("id") or "")
        if not pid or pid == selected_id:
            continue
        queue.append(
            {
                "id": pid,
                "title": str(p.get("title") or pid),
                "difficulty": str(p.get("difficulty") or "Easy"),
                "tags": list(p.get("tags") or []),
                "reason": "Not solved yet" if pid not in solved else "Revision suggested",
                "score": 2 if pid not in solved else 1,
            }
        )
        if len(queue) >= max(1, int(limit)):
            break
    return queue


def _light_contest_snapshot(problems: list) -> dict[str, Any]:
    chosen = []
    for d in ("Easy", "Medium", "Hard"):
        for p in problems:
            if str((p or {}).get("difficulty") or "") == d:
                chosen.append(p)
                break
    if not chosen:
        chosen = list(problems[:3])
    return {
        "contest": {
            "id": "local",
            "title": "Weekly Contest (Preview)",
            "problem_ids": [str(p.get("id") or "") for p in chosen],
            "problems": [
                {"id": str(p.get("id") or ""), "title": str(p.get("title") or ""), "difficulty": str(p.get("difficulty") or "Easy")}
                for p in chosen
            ],
            "start_ts": 0,
            "end_ts": 0,
        },
        "leaderboard": [],
        "user_rank": 0,
        "user_percentile": 0.0,
    }


def coding_context_payload(request: Request, problem_id: str, **extra):
    attempts = request.session.get("coding_attempts", [])
    problems = _safe_call(get_all_problems, list(DEFAULT_PROBLEMS))
    selected = _select_problem(problems, problem_id)
    email = (request.session.get("user_email") or "").strip().lower()
    language = request.session.get(f"lang_{selected['id']}", "python")
    if language not in SUPPORTED_LANGUAGES:
        language = "python"
    code_key = f"code_{selected['id']}_{language}"
    problem_attempts = [a for a in attempts if a.get("problem_id") == selected["id"]][:12]
    timed_state = _timed_mode_state(request, selected["id"])
    solved = set(
        a.get("problem_id")
        for a in attempts
        if a.get("mode") == "submit" and a.get("status") == "Accepted"
    )
    solved_count = len(solved)
    if CODING_DEEP_INSIGHTS and email:
        solved_count = _safe_call(_solved_problem_count, solved_count, email)

    summary_default = {
        "total": 0,
        "accepted": 0,
        "accept_rate": 0.0,
        "avg_runtime_ms": 0.0,
        "by_language": [],
        "recent": [],
    }
    user_summary = _safe_call(get_user_submission_summary, summary_default, email) if email else summary_default

    if CODING_DEEP_INSIGHTS and email:
        problem_timeline = _safe_call(get_problem_timeline, [], email, selected["id"], 12)
        weak = _safe_call(weak_tags_for_user, [], email, 30)
        readiness = _safe_call(interview_readiness_score, _readiness_from_summary(user_summary), email)
        plan_7 = _safe_call(study_plan, ["Day 1-2: Solve 2 Easy problems.", "Day 3-4: Solve 2 Medium problems."], email, 7)
        plan_30 = _safe_call(study_plan, ["Week 1: Foundation review.", "Week 2: Medium optimization practice."], email, 30)
        recommended = _safe_call(recommend_next_problem, _recommended_from_problems(problems, selected["id"], attempts), email, selected["id"])
        queue = _safe_call(personalized_practice_queue, _practice_queue_from_problems(problems, selected["id"], attempts, 5), email, selected["id"], 5)
        mastery = _safe_call(topic_mastery_report, [], email, 45)
        daily_goal = _safe_call(daily_goal_progress, _daily_goal_from_attempts(attempts), email)
        contest = _safe_call(contest_snapshot, _light_contest_snapshot(problems), email, 10)
    else:
        problem_timeline = []
        weak = []
        readiness = _readiness_from_summary(user_summary)
        plan_7 = ["Day 1-2: Solve 2 Easy problems.", "Day 3-4: Solve 2 Medium problems.", "Day 5-7: Review failures and retry."]
        plan_30 = ["Week 1: Build fundamentals.", "Week 2: Medium problems.", "Week 3: Timed sets.", "Week 4: Mock interview drills."]
        recommended = _recommended_from_problems(problems, selected["id"], attempts)
        queue = _practice_queue_from_problems(problems, selected["id"], attempts, 5)
        mastery = []
        daily_goal = _daily_goal_from_attempts(attempts)
        contest = _light_contest_snapshot(problems)

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
        "problem_timeline": problem_timeline,
        "solved_count": solved_count,
        "last_custom_input": request.session.get(f"custom_input_{selected['id']}", ""),
        "user_submission_summary": user_summary,
        "weak_tags": weak,
        "readiness": readiness,
        "study_plan_7d": plan_7,
        "study_plan_30d": plan_30,
        "recommended_problem": recommended,
        "practice_queue": queue,
        "mastery": mastery,
        "daily_goal": daily_goal,
        "contest_snapshot": contest,
        "problem_coverage": coverage_report(selected),
        "submit_idem_key": f"submit-{int(time.time()*1000)}-{uuid.uuid4().hex[:10]}",
        "timed_state": timed_state,
        "timed_mode": str(timed_state.get("duration_min") or "") if timed_state.get("enabled") else "",
        "user_plan": current_user_plan(request),
    }
    payload.update(extra)
    return payload


def admin_context_payload(request: Request, minimal: bool = False, include_coding_problems: bool = False):
    raw_data = get_bookings()
    # Ensure meet URLs in bookings data never contain unencoded spaces
    data = []
    for row in raw_data:
        if isinstance(row, (list, tuple)) and len(row) > 5 and isinstance(row[5], str):
            row_list = list(row)
            row_list[5] = row_list[5].replace(" ", "-")
            data.append(tuple(row_list) if isinstance(row, tuple) else row_list)
        else:
            data.append(row)

    is_demo = False

    if minimal:
        payload = {
            "kpis": {"total_bookings": len(data)},
            "user_stats": {"total": 3, "admins": 1, "mentors": 1, "premium": 1},
        }
    else:
        payload = dashboard_payload(data)
        if not payload.get("user_stats"):
            payload["user_stats"] = {"total": 3, "admins": 1, "mentors": 1, "premium": 1}

    coding_stats = {
        "total_submissions": 0,
        "by_difficulty": [],
        "by_language": [],
        "by_problem": [],
    }
    custom_problems = []
    if include_coding_problems:
        coding_stats = get_submission_stats_extended(limit=100)
        custom_problems = get_custom_problems()
        for p in custom_problems:
            p["coverage"] = coverage_report(p)

    is_demo = False

    return {
        "request": request,
        "data": data,
        "admin": payload,
        "coding_stats": coding_stats,
        "custom_problems": custom_problems,
        "is_demo": is_demo,
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


def extract_text_from_latex(code: str) -> str:
    """Extracts human-readable text from LaTeX code for ATS keyword parsing and scoring."""
    if not code:
        return ""
    # Strip preamble if standard LaTeX document
    if r"\begin{document}" in code:
        code = code.split(r"\begin{document}", 1)[1]
    if r"\end{document}" in code:
        code = code.split(r"\end{document}", 1)[0]
    lines = []
    for line in code.splitlines():
        trimmed = line.strip()
        if trimmed.startswith('%'):
            continue
        idx = line.find('%')
        if idx != -1 and (idx == 0 or line[idx - 1] != '\\'):
            line = line[:idx]
        lines.append(line)
    text = '\n'.join(lines)
    # Extract href text: \href{url}{text} -> text (url)
    def _replace_href(m):
        url = m.group(1).strip()
        label = m.group(2).strip()
        if url.startswith("mailto:"):
            return label
        return f"{label} ({url})"

    text = re.sub(r'\\href\{([^{}]*)\}\{([^{}]*)\}', _replace_href, text)
    # Strip common command tags with arguments
    for _ in range(4):
        text = re.sub(r'\\[a-zA-Z]+\*?\{([^{}]*)\}', r'\1', text)
    # Strip standalone commands
    text = re.sub(r'\\[a-zA-Z]+', ' ', text)
    # Strip brackets and symbols
    text = text.replace('{', ' ').replace('}', ' ').replace('&', ' ').replace('\\', ' ')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()
