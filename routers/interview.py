from fastapi import APIRouter, Request, Form, UploadFile, File, BackgroundTasks, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
import os
import uuid
import json
import time

# Modular imports
from core import templates, logger
from db import (
    get_latest_resume_report_for_user,
    get_user_memory,
    save_user_memory,
    get_user_weaknesses,
    is_premium_user,
    get_conn
)
from features.shared.analytics import log_event, log_model_health
from features.shared import parse_json_object
from features.interview import (
    generate_interviewer_response,
    generate_opener,
    score_candidate_questions,
    generate_questions,
    generate_follow_up,
    generate_lifeline_hints,
    grade_answer,
    analyze_answer,
    hiring_decision,
    generate_ideal_answer,
    bank_questions,
    interview_metrics,
    build_pre_session_brief,
    interview_context_payload
)

# normalize_question was used in old core.py, moved to features.shared or implemented here
def normalize_question(q):
    if isinstance(q, dict):
        q = q.get("question", "")
    q = str(q)
    q = q.replace("\n", " ")
    q = q.replace("Question:", "")
    q = q.strip()
    return q

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
        return templates.TemplateResponse(request=request, name="interview.html", context=interview_context_payload(request))

    request.session["questions"] = questions
    request.session["ideal"] = []
    request.session["current"] = 0
    request.session["timeline"] = []
    request.session["finished"] = False
    request.session["final_score"] = None
    request.session["hiring_result"] = None
    request.session["last_feedback"] = None
    request.session["next_followup"] = None
    
    user_email = (request.session.get("user_email") or "").strip().lower()
    resume_report = get_latest_resume_report_for_user(user_email) or request.session.get("last_resume_report", {})
    request.session["resume_context"] = (resume_report.get("fixed_resume_md", "") or resume_report.get("resume_text", ""))[:2000]
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

    return templates.TemplateResponse(request=request, name="interview.html", context=interview_context_payload(request))

@router.get("/interview/new")
def new_interview(request: Request):
    keys_to_clear = [
        "questions", "ideal", "current", "answers", "scores", 
        "timeline", "finished", "final_score", "hiring_result", 
        "last_feedback", "next_followup", "interview_config"
    ]
    for key in keys_to_clear:
        request.session.pop(key, None)
    return RedirectResponse(url="/interview", status_code=303)

@router.post("/interview/start", response_class=JSONResponse)
def interview_start(request: Request):
    """Called by the frontend on page load to get the opener message."""
    session_email = (request.session.get("user_email") or "").strip().lower()
    if not session_email:
        return JSONResponse({"error": "not authenticated"}, status_code=403)

    config = request.session.get("interview_config", {})
    persona = str(config.get("persona", "Neutral"))
    opener = generate_opener(config, persona)

    session_id_val = request.session.get("interview_id")
    if session_id_val:
        for attempt in range(3):
            try:
                from db import backend as db_core
                db_conn = get_conn()
                cur = db_conn.cursor()
                history = [{"speaker": "interviewer", "text": opener}]
                db_core.execute(cur, "UPDATE interview_sessions SET chat_history_json=? WHERE session_id=? AND user_email=?",
                           (json.dumps(history), session_id_val, session_email))
                db_conn.commit()
                break # Success
            except Exception as e:
                print(f"INTERVIEW START DB ERR (attempt {attempt+1}): {e}")
                time.sleep(0.1)

    request.session["chat_phase"] = "warmup"
    request.session["chat_topics_covered"] = 0
    return JSONResponse({"reply": opener, "phase": "warmup"})

def _trim_history(history: list, keep_recent: int = 9) -> list:
    """Always keep the opener (turn 0) + the most recent keep_recent turns."""
    if len(history) <= keep_recent + 1:
        return history
    opener = history[:1]
    recent = history[-(keep_recent):]
    return opener + recent

def _next_phase(current_phase: str, topics_covered: int, max_rounds: int) -> str:
    if current_phase == "warmup":
        return "interview"
    if current_phase == "interview":
        if topics_covered >= max_rounds:
            return "closing"
        return "interview"
    if current_phase == "closing":
        return "questions_for_me"
    if current_phase == "questions_for_me":
        return "done"
    if current_phase in ("done",):
        return "done"
    return "interview"

@router.post("/interview/chat-json", response_class=JSONResponse)
async def interview_chat_json(request: Request):
    """Process one candidate turn and return next interviewer message."""
    session_email = (request.session.get("user_email") or "").strip().lower()
    if not session_email:
        return JSONResponse({"error": "not authenticated"}, status_code=403)

    current_phase = request.session.get("chat_phase", "warmup")
    if current_phase == "done":
        return JSONResponse({"error": "session already completed", "phase": "done"}, status_code=400)

    config = request.session.get("interview_config", {})
    persona = str(config.get("persona", "Neutral"))
    max_rounds = int(config.get("max_rounds", 5))

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON body"}, status_code=400)

    candidate_message = str(body.get("message", "")).strip()
    if not candidate_message:
        return JSONResponse({"error": "empty message"}, status_code=400)

    conversation_history = body.get("conversation_history", [])
    if not isinstance(conversation_history, list):
        conversation_history = []

    conversation_history.append({"speaker": "candidate", "text": candidate_message})
    interviewer_turns = [t for t in conversation_history if t.get("speaker") == "interviewer"]
    topics_covered = max(0, len(interviewer_turns) - 1)
    next_phase = _next_phase(current_phase, topics_covered, max_rounds)
    trimmed = _trim_history(conversation_history, keep_recent=9)

    if next_phase == "done":
        reply = ("Great \u2014 thanks so much for your time today. "
                 "You\u2019ll hear back from us within a few days. Have a good rest of your day.")
    else:
        reply = generate_interviewer_response(
            conversation_history=trimmed,
            config=config,
            persona=persona,
            phase=next_phase,
        )

    conversation_history.append({"speaker": "interviewer", "text": reply})
    request.session["chat_phase"] = next_phase
    request.session["chat_topics_covered"] = topics_covered

    session_id_val = request.session.get("interview_id")
    if session_id_val:
        for attempt in range(3):
            try:
                from db import backend as db_core
                db_conn = get_conn()
                cur = db_conn.cursor()
                db_core.execute(cur,
                           "UPDATE interview_sessions SET chat_history_json=? WHERE session_id=? AND user_email=?",
                           (json.dumps(conversation_history), session_id_val, session_email))
                db_conn.commit()
                break # Success
            except Exception as e:
                print(f"CHAT DB SAVE ERR (attempt {attempt+1}): {e}")
                time.sleep(0.1)

    return JSONResponse({"reply": reply, "phase": next_phase, "topics_covered": topics_covered})

@router.post("/interview/finish", response_class=JSONResponse)
async def interview_finish(request: Request, db_conn=Depends(get_conn)):
    """Score the full conversation and return verdict + breakdown."""
    import asyncio
    session_email = (request.session.get("user_email") or "").strip().lower()
    if not session_email:
        return JSONResponse({"error": "not authenticated"}, status_code=403)

    config = request.session.get("interview_config", {})
    role = str(config.get("role", "Engineer"))
    company = str(config.get("company", "the company"))
    session_id_val = request.session.get("interview_id")

    try:
        body = await request.json()
    except Exception:
        body = {}

    conversation_history = body.get("conversation_history", [])
    if not isinstance(conversation_history, list):
        conversation_history = []

    candidate_questions_text = str(body.get("candidate_questions", "")).strip()

    if not conversation_history:
        return JSONResponse({
            "error": "no conversation to score",
            "final_score": 0.0,
            "hiring_result": {"decision": "No Hire", "confidence": "Low", "summary": "No interview data.", "panel_notes": []},
            "qa_history": [],
            "questions_score": {"score": 0, "notes": "No conversation provided."},
        }, status_code=200)

    if session_id_val:
        try:
            from db import backend as db_core
            cur = db_conn.cursor()
            db_core.execute(cur, "SELECT user_email FROM interview_sessions WHERE session_id=?", (session_id_val,))
            row = cur.fetchone()
            if row and row[0] and row[0].strip().lower() != session_email:
                return JSONResponse({"error": "forbidden"}, status_code=403)
        except Exception:
            pass

    qa_history = []
    scored_timeline = []
    partial = False

    async def score_all():
        nonlocal partial
        deadline = asyncio.get_event_loop().time() + 45.0
        last_interviewer_q = f"Tell me about your approach to {config.get('topic', 'General')}."
        candidate_count = 0
        
        for turn in conversation_history:
            if asyncio.get_event_loop().time() > deadline:
                partial = True
                break
            speaker = turn.get("speaker")
            if speaker == "interviewer":
                last_interviewer_q = turn.get("text", "")
            elif speaker == "candidate":
                answer = turn.get("text", "")
                try:
                    ideal = await asyncio.to_thread(generate_ideal_answer, last_interviewer_q) if last_interviewer_q else "N/A"
                except Exception:
                    ideal = "N/A"
                try:
                    result = await asyncio.to_thread(
                        analyze_answer,
                        question=last_interviewer_q,
                        answer=answer,
                        ideal_answer=ideal,
                        round_type=str(config.get("round_type", "technical")),
                        answer_time_sec=0,
                    )
                except Exception:
                    result = {"overall": 5.0, "rubric": {}, "strengths": [], "improvements": []}

                candidate_count += 1
                qa_history.append({
                    "round": candidate_count,
                    "question": last_interviewer_q,
                    "user_answer": answer,
                    "ideal_answer": ideal,
                    "score": result.get("overall", 0),
                    "rubric": result.get("rubric", {}),
                    "strengths": result.get("strengths", []),
                    "improvements": result.get("improvements", []),
                })
                scored_timeline.append({"overall": result.get("overall", 0), "score": result.get("overall", 0)})

    await score_all()

    q_score = {"score": 5, "notes": ""}
    if candidate_questions_text:
        try:
            q_score = await asyncio.to_thread(score_candidate_questions, candidate_questions_text, role, company)
        except Exception:
            pass

    total = sum(float(s.get("overall", s.get("score", 0))) for s in scored_timeline)
    count = max(1, len(scored_timeline))
    final_score = round(total / count, 1) if scored_timeline else 0.0
    hiring_result = hiring_decision(scored_timeline)
    hiring_result["curiosity_score"] = q_score

    if session_id_val:
        try:
            from db import backend as db_core
            cur = db_conn.cursor()
            db_core.execute(cur,
                       "UPDATE interview_sessions SET qa_history_json=?, overall_score=? WHERE session_id=? AND user_email=?",
                       (json.dumps(qa_history), final_score, session_id_val, session_email))
            db_conn.commit()
        except Exception as e:
            print(f"FINISH DB ERR: {e}")

    request.session["finished"] = True
    request.session["final_score"] = final_score
    request.session["hiring_result"] = hiring_result

    return JSONResponse({
        "final_score": final_score,
        "hiring_result": hiring_result,
        "qa_history": qa_history,
        "questions_score": q_score,
        "partial": partial,
    })

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
    db_conn = Depends(get_conn),
):
    start = time.time()
    is_prem = is_premium_user(request)
    max_rounds = max(3, min(8, int(max_rounds)))
    if persona == "Pressure Test" and not is_prem:
        return templates.TemplateResponse(
            request=request,
            name="interview.html",
            context=interview_context_payload(request, premium_notice="Pressure Test mode is Premium only."),
        )
    if max_rounds > 3 and not is_prem:
        return templates.TemplateResponse(
            request=request,
            name="interview.html",
            context=interview_context_payload(request, premium_notice="More than 3 rounds requires Premium."),
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
    past_weaknesses = get_user_weaknesses(user_email) if user_email else []
    skill_gaps = list(set(skill_gaps + past_weaknesses))[:5]
    resume_context = resume_report.get("fixed_resume_md", "") or resume_report.get("resume_text", "")

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
        resume_context=resume_context[:2000],
    )
    questions = [normalize_question(q) for q in questions if str(q).strip()]
    questions = seeded + questions
    deduped = []
    seen = set()
    for q in questions:
        key = q.lower()
        if key in seen: continue
        seen.add(key)
        deduped.append(q)
    questions = deduped[: max(1, min(3, max_rounds))]
    if not questions:
        questions = [f"Tell me about your approach to {topic}."]

    session_id_val = str(uuid.uuid4())
    request.session["interview_id"] = session_id_val
    if user_email:
        from db import backend as db_core
        cur = db_conn.cursor()
        now = int(time.time())
        db_core.execute(cur, "INSERT INTO interview_sessions (session_id, user_email, topic, difficulty, overall_score, qa_history_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (session_id_val, user_email, topic, difficulty, 0.0, "[]", now))
        db_conn.commit()

    request.session["questions"] = questions
    request.session["current"] = 0
    request.session["timeline"] = []
    request.session["finished"] = False
    request.session["final_score"] = None
    request.session["hiring_result"] = None
    request.session["last_feedback"] = None
    request.session["next_followup"] = None
    request.session["interview_config"] = {
        "topic": topic, "role": role, "company": company, "round_type": round_type,
        "difficulty": difficulty, "persona": persona, "max_rounds": max_rounds,
        "skill_gaps": skill_gaps, "fixed_questions": False,
    }
    log_event("interview_started", "mock_interview", role=role or "", metadata={"topic": topic, "max_rounds": max_rounds})
    log_model_health("mock_interview_question_gen", "openai/gpt-4o-mini", success=True, latency_ms=(time.time() - start) * 1000.0)

    return templates.TemplateResponse(request=request, name="interview.html", context=interview_context_payload(request))

@router.post("/evaluate", response_class=HTMLResponse)
def evaluate(request: Request,
             question: str = Form(...),
             answer: str = Form(...),
             answer_time_sec: float = Form(0.0),
             db_conn = Depends(get_conn)):
    start = time.time()
    request.session.pop("resume_versions", None)
    request.session.pop("audit_logs", None)
    
    questions = request.session.get("questions", [])
    current = request.session.get("current", 0)
    timeline = request.session.get("timeline", [])
    config = request.session.get("interview_config", {})
    max_rounds = int(config.get("max_rounds", max(len(questions), 5)))

    if not questions:
        return templates.TemplateResponse(request=request, name="interview.html", context=interview_context_payload(request))

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_ideal = executor.submit(generate_ideal_answer, question)
        future_followup = executor.submit(
            generate_follow_up,
            question=question,
            answer=answer,
            topic=str(config.get("topic", "General")),
            role=str(config.get("role", "")),
            round_type=str(config.get("round_type", "technical")),
            persona=str(config.get("persona", "Neutral")),
        )
        try:
            ideal_answer = future_ideal.result(timeout=10)
        except Exception:
            ideal_answer = "Explain your approach clearly with tradeoffs and impact."
        ideal_answer = normalize_question(ideal_answer)

        result = analyze_answer(
            question=question,
            answer=answer,
            ideal_answer=ideal_answer,
            round_type=str(config.get("round_type", "technical")),
            answer_time_sec=float(answer_time_sec or 0),
        )
        try: next_followup = future_followup.result(timeout=10)
        except Exception: next_followup = None

    min_result = {"overall": result.get("overall", 0), "voice_pace": result.get("voice_pace", {})}
    timeline = timeline + [min_result]
    current += 1

    request.session["current"] = current
    request.session["timeline"] = timeline

    adaptive_difficulty = str(config.get("difficulty", "intermediate"))
    overall_now = float(result.get("overall", 0))
    if overall_now >= 8: adaptive_difficulty = "advanced"
    elif overall_now <= 5: adaptive_difficulty = "beginner"
    config["adaptive_difficulty"] = adaptive_difficulty
    request.session["interview_config"] = config
    request.session["next_followup"] = next_followup

    finished = current >= max_rounds
    final_score = 0.0
    hiring_result = None

    if not finished:
        if not bool(config.get("fixed_questions", False)):
            user_email = (request.session.get("user_email") or "").strip().lower()
            resume_report = get_latest_resume_report_for_user(user_email) if user_email else {}
            resume_context = (resume_report.get("fixed_resume_md", "") or resume_report.get("resume_text", ""))[:2000] if resume_report else ""
            next_q = generate_questions(
                topic=str(config.get("topic", "General")),
                role=str(config.get("role", "")),
                company=str(config.get("company", "")),
                round_type=str(config.get("round_type", "technical")),
                difficulty=adaptive_difficulty,
                persona=str(config.get("persona", "Neutral")),
                skill_gaps=list(config.get("skill_gaps", [])),
                num_questions=1,
                resume_context=resume_context,
            )
            next_q = [normalize_question(q) for q in next_q if str(q).strip()]
            if next_q: questions = questions + [next_q[0]]
            request.session["questions"] = questions
    else:
        eval_timeline = timeline
        total = sum([float(s.get("overall", s.get("score", 0))) for s in eval_timeline])
        final_score = round(total / max(1, len(eval_timeline)), 1)
        hiring_result = hiring_decision(eval_timeline)
        request.session["final_score"] = final_score
        request.session["hiring_result"] = hiring_result
        request.session["finished"] = True

    session_id_val = request.session.get("interview_id")
    if session_id_val:
        from db import backend as db_core
        cur = db_conn.cursor()
        db_core.execute(cur, "SELECT qa_history_json FROM interview_sessions WHERE session_id=?", (session_id_val,))
        row = cur.fetchone()
        if row:
            try: hist = json.loads(row[0])
            except Exception: hist = []
            hist.append({
                "round": len(timeline),
                "question": question,
                "user_answer": answer,
                "ideal_answer": ideal_answer,
                "score": result.get("overall", 0),
                "feedback": result.get("improvements", ["Solid performance"])[0] if result.get("improvements") else "Solid performance"
            })
            db_core.execute(cur, "UPDATE interview_sessions SET qa_history_json=?, overall_score=? WHERE session_id=?", (json.dumps(hist), final_score or 0.0, session_id_val))
            db_conn.commit()

        log_event("interview_round_scored", "mock_interview", metadata={"round": current, "overall": result.get("overall", 0)})

    log_model_health("mock_interview_eval", "embedding+heuristics", success=True, latency_ms=(time.time() - start) * 1000.0)

    return templates.TemplateResponse(request=request, name="interview.html", context=interview_context_payload(
        request, feedback=result, finished=finished, final_score=final_score, hiring_result=hiring_result, next_followup=next_followup
    ))

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
        log_event("honeypot_triggered", "mentorship")
        return templates.TemplateResponse(request=request, name="book_call.html", context={"request": request, "error": "Request blocked.", "prefill": {}})
    
    from db.booking import save_booking
    from features.shared.email import send_mail
    start = time.time()
    room = f"mock-{topic}-{int(time.time())}"
    link = f"https://meet.jit.si/{room}"
    brief = build_pre_session_brief(name, email, topic, datetime, outcome, context_notes, link)
    save_booking(name, email, topic, datetime, link, outcome=outcome, context_notes=context_notes, brief=brief)
    
    user_body = f"Mentorship session booked.\nLink: {link}\nBrief: {brief}"
    background_tasks.add_task(send_mail, email, link, "Mentorship Session Confirmed", user_body)
    log_event("mentor_booking_created", "mentorship", user_id=email)
    log_model_health("mentorship_booking", "app_internal", success=True, latency_ms=(time.time() - start) * 1000.0)

    return templates.TemplateResponse(request=request, name="book_call.html", context={"request": request, "prefill": {"name": name, "email": email, "topic": topic}})

@router.get("/book-call", response_class=HTMLResponse)
def book_call_page(request: Request):
    return templates.TemplateResponse(request=request, name="book_call.html", context={"request": request, "prefill": {}})
