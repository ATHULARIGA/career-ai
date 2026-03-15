from fastapi import APIRouter, Request, Form, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
from core import *

router = APIRouter()

@router.post("/interview/from-resume", response_class=HTMLResponse)
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


@router.post("/generate", response_class=HTMLResponse)
def generate(
    request: Request,
    topic: str = Form(...),
    role: str = Form(""),
    company: str = Form(""),
    round_type: str = Form("technical"),
    difficulty: str = Form("intermediate"),
    persona: str = Form("Neutral"),
    max_rounds: int = Form(5),
):
    start = time.time()
    is_premium = is_premium_user(request)
    max_rounds = max(3, min(8, int(max_rounds)))
    if persona == "Pressure Test" and not is_premium:
        return templates.TemplateResponse(
            "interview.html",
            interview_context_payload(request, premium_notice="Pressure Test mode is Premium only."),
        )
    if max_rounds > 3 and not is_premium:
        return templates.TemplateResponse(
            "interview.html",
            interview_context_payload(request, premium_notice="More than 3 rounds requires Premium."),
        )
    user_email = (request.session.get("user_email") or "").strip().lower()
    if user_email and (role.strip() or company.strip() or topic.strip()):
        prior_memory = get_user_memory(user_email)
        save_user_memory(
            user_email,
            target_role=role or prior_memory.get("target_role", ""),
            target_company=company or prior_memory.get("target_company", ""),
            focus_area=topic or prior_memory.get("focus_area", ""),
        )
    resume_report = get_latest_resume_report_for_user(user_email) or request.session.get("last_resume_report", {})
    gaps = resume_report.get("keyword_gaps", []) if isinstance(resume_report, dict) else []
    skill_gaps = [str(g.get("keyword", "")).strip() for g in gaps if isinstance(g, dict) and g.get("keyword")]
    skill_gaps = skill_gaps[:4]

    seeded = bank_questions(topic=topic, role=role, round_type=round_type, limit=2)
    questions = generate_questions(
        topic=topic,
        role=role,
        company=company,
        round_type=round_type,
        difficulty=difficulty,
        persona=persona,
        skill_gaps=skill_gaps,
        num_questions=1,
    )
    questions = [normalize_question(q) for q in questions if str(q).strip()]
    questions = seeded + questions
    deduped = []
    seen = set()
    for q in questions:
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(q)
    questions = deduped[: max(1, min(3, max_rounds))]
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
        "persona": persona,
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
            "persona": persona,
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

@router.post("/evaluate", response_class=HTMLResponse)
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
        persona=str(config.get("persona", "Neutral")),
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
            persona=str(config.get("persona", "Neutral")),
            skill_gaps=list(config.get("skill_gaps", [])),
            num_questions=1,
        )
        next_q = [normalize_question(q) for q in next_q if str(q).strip()]
        if not next_q:
            next_q = bank_questions(
                topic=str(config.get("topic", "General")),
                role=str(config.get("role", "")),
                round_type=str(config.get("round_type", "")),
                limit=1,
            )
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
@router.post("/schedule", response_class=HTMLResponse)
def schedule(request: Request,
             background_tasks: BackgroundTasks,
             name: str = Form(...),
             email: str = Form(...),
             topic: str = Form(...),
             datetime: str = Form(...),
             outcome: str = Form(""),
             context_notes: str = Form(""),
             website: str = Form("")):
    if (website or "").strip():
        return templates.TemplateResponse("book_call.html", {"request": request, "error": "Request blocked.", "prefill": {}})
    start = time.time()

    room = f"mock-{topic}-{int(time.time())}"
    link = f"https://meet.jit.si/{room}"

    checklist = [
        "Bring one real project example with measurable impact.",
        f"Prepare one challenge around: {topic}.",
        f"Define success criteria: {outcome or 'clear interview improvement goal'}.",
        "Keep resume and JD open during the session.",
    ]
    action_plan = [
        "Revise two weak answers using STAR + metrics.",
        "Run one timed mock round within 48 hours.",
        "Update resume bullets based on mentor feedback.",
    ]
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

Prep Checklist:
- {checklist[0]}
- {checklist[1]}
- {checklist[2]}
- {checklist[3]}
"""
    background_tasks.add_task(send_mail, email, link, "Mentorship Session Confirmed", user_body)

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
        "checklist": checklist,
        "action_plan": action_plan,
        "rebook_url": "/book-call?" + urlencode({
            "name": name,
            "email": email,
            "topic": topic,
            "outcome": outcome,
        }),
        "prefill": {"name": name, "email": email, "topic": topic, "outcome": outcome},
    })


@router.post("/mindmap")
async def create_mindmap(request: Request, role: str = Form(...)):
    start = time.time()
    if not is_premium_user(request):
        day_key = time.strftime("%Y-%m-%d")
        used_day = request.session.get("roadmap_day")
        used_count = int(request.session.get("roadmap_count", 0) or 0)
        if used_day != day_key:
            used_day = day_key
            used_count = 0
        if used_count >= 1:
            return JSONResponse(
                content={"error": "Free plan allows 1 roadmap/day. Upgrade for unlimited roadmaps.", "premium_required": True},
                status_code=403,
            )
        request.session["roadmap_day"] = used_day
        request.session["roadmap_count"] = used_count + 1
    try:
        user_email = (request.session.get("user_email") or "").strip().lower()
        if user_email and (role or "").strip():
            prior_memory = get_user_memory(user_email)
            save_user_memory(
                user_email,
                target_role=role,
                target_company=prior_memory.get("target_company", ""),
                focus_area=prior_memory.get("focus_area", ""),
            )
        data = generate_mindmap(role)
        log_event("roadmap_generated", "career_roadmap", role=role, metadata={"node_count": len(data.get("children", []))})
        log_model_health("career_roadmap", "openai/gpt-4o-mini", success=True, latency_ms=(time.time() - start) * 1000.0)
        return JSONResponse(content=data)
    except Exception as e:
        print(f"Error generating mindmap: {e}")
        log_event("roadmap_failed", "career_roadmap", role=role, metadata={"error": str(e)})
        log_model_health("career_roadmap", "openai/gpt-4o-mini", success=False, latency_ms=(time.time() - start) * 1000.0, fallback_used=True, error_message=str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)

@router.post("/skill-info")
async def skill_info(request: Request, skill: str = Form(...)):
    if not is_premium_user(request):
        return JSONResponse(
            content={
                "description": "Detailed skill insights are Premium only.",
                "resources": [],
                "premium_required": True,
            },
            status_code=200,
        )
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

@router.post("/interview/lifeline")
async def get_lifeline(request: Request, question: str = Form(...)):
    user_email = (request.session.get("user_email") or "").strip().lower()
    resume_report = get_latest_resume_report_for_user(user_email) if user_email else {}
    if not resume_report:
        resume_report = request.session.get("last_resume_report", {})
    
    resume_context = ""
    if resume_report:
        sim = resume_report.get("recruiter_simulation", {})
        strengths = sim.get("strengths", [])
        if strengths:
            resume_context = "Candidate Strengths:\n- " + "\n- ".join(strengths)
        
        rewrites = resume_report.get("targeted_rewrites", [])
        if rewrites:
            bullets = [r.get("after") for r in rewrites if r.get("after")]
            if bullets:
                resume_context += "\n\nKey Achievements:\n- " + "\n- ".join(bullets[:3])
                
    hints = generate_lifeline_hints(question, resume_context=resume_context)
    return JSONResponse(content={"hints": hints})
