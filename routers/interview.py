import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)

from core import *
from core.database import (
    delete_user_cheatsheet,
    get_user_cheatsheets,
    save_user_cheatsheet,
    update_cheatsheet_revised,
)
from services.interview.cheatsheet_generator import (
    build_standalone_cheatsheet_html,
    extract_technologies_from_resume,
    get_cheatsheet_for_technology,
)
from services.interview.ideal_generator import generate_ideal_answer
from services.interview.interview_engine import (
    generate_interviewer_response,
    generate_opener,
    score_candidate_questions,
)
from services.interview.interview_feedback import analyze_answer, hiring_decision

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

import db.backend as db


@router.post("/interview/start", response_class=JSONResponse)
def interview_start(request: Request):
    """Called by the frontend on page load to get the opener message."""
    # Gap 1: auth check — user must own this session
    session_email = (request.session.get("user_email") or "").strip().lower()
    if not session_email:
        return JSONResponse({"error": "not authenticated"}, status_code=403)

    config = request.session.get("interview_config", {})
    persona = str(config.get("persona", "Neutral"))
    opener = generate_opener(config, persona)

    session_id_val = request.session.get("interview_id")
    if session_id_val:
        import time
        for attempt in range(3):
            try:
                db_conn = db.get_conn()
                cur = db_conn.cursor()
                history = [{"speaker": "interviewer", "text": opener}]
                db.execute(cur, "UPDATE interview_sessions SET chat_history_json=? WHERE session_id=? AND user_email=?",
                           (json.dumps(history), session_id_val, session_email))
                db_conn.commit()
                break # Success
            except Exception as e:
                print(f"INTERVIEW START DB ERR (attempt {attempt+1}): {e}")
                if attempt == 2: pass # last try. don't block start but log error
                time.sleep(0.1)

    request.session["chat_phase"] = "warmup"
    request.session["chat_topics_covered"] = 0
    return JSONResponse({"reply": opener, "phase": "warmup"})


# ---------------------------------------------------------------------------
# Gap 2: helper — truncate history to opener + last N turns
# ---------------------------------------------------------------------------
def _trim_history(history: list[Any], keep_recent: int = 9) -> list[Any]:
    """Always keep the opener (turn 0) + the most recent keep_recent turns."""
    if len(history) <= keep_recent + 1:
        return history
    opener = history[:1]
    recent = history[-(keep_recent):]
    return opener + recent


# ---------------------------------------------------------------------------
# Gap 3: explicit phase transition logic
# ---------------------------------------------------------------------------
def _next_phase(current_phase: str, topics_covered: int, max_rounds: int) -> str:
    """
    Phase machine:
      warmup            → interview  (after candidate's first response)
      interview         → closing    (after max_rounds topics covered)
      closing           → questions_for_me (after candidate submits their questions)
      questions_for_me  → done
      done              → done (terminal; reject further messages on the caller side)
    Edge: any other value maps to interview (graceful fallback)
    """
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
    # Graceful fallback: e.g. "End Interview" clicked during warmup
    if current_phase in ("done",):
        return "done"
    return "interview"


@router.post("/interview/chat-json", response_class=JSONResponse)
async def interview_chat_json(request: Request):
    """Process one candidate turn and return next interviewer message."""
    # Gap 1: auth check
    session_email = (request.session.get("user_email") or "").strip().lower()
    if not session_email:
        return JSONResponse({"error": "not authenticated"}, status_code=403)

    # Gap 6: reject messages after session is over
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
    # Gap 6: empty message → 400
    if not candidate_message:
        return JSONResponse({"error": "empty message"}, status_code=400)

    conversation_history = body.get("conversation_history", [])
    # Validate types to prevent injection of bad history shapes
    if not isinstance(conversation_history, list):
        conversation_history = []

    # Append candidate message to full history
    conversation_history.append({"speaker": "candidate", "text": candidate_message})

    # Count interviewer turns to determine topics covered
    # Opener = 1st interviewer turn; each subsequent interviewer turn = 1 topic question
    interviewer_turns = [t for t in conversation_history if t.get("speaker") == "interviewer"]
    topics_covered = max(0, len(interviewer_turns) - 1)

    # Gap 3: use explicit phase machine
    next_phase = _next_phase(current_phase, topics_covered, max_rounds)

    # Gap 2: truncate history before sending to AI (keep opener + last 9)
    trimmed = _trim_history(conversation_history, keep_recent=9)

    # Generate reply
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

    # Persist full (un-trimmed) conversation to DB, keyed by session + email (Gap 1)
    session_id_val = request.session.get("interview_id")
    if session_id_val:
        for attempt in range(3):
            try:
                db_conn = db.get_conn()
                cur = db_conn.cursor()
                db.execute(cur,
                           "UPDATE interview_sessions SET chat_history_json=? WHERE session_id=? AND user_email=?",
                           (json.dumps(conversation_history), session_id_val, session_email))
                db_conn.commit()
                break # Success
            except Exception as e:
                print(f"CHAT DB SAVE ERR (attempt {attempt+1}): {e}")
                if attempt == 2: pass # last try; don't return 500 but log error
                await asyncio.sleep(0.1)

    return JSONResponse({"reply": reply, "phase": next_phase, "topics_covered": topics_covered})


@router.post("/interview/finish", response_class=JSONResponse)
async def interview_finish(request: Request, db_conn=Depends(db.get_conn)):
    """Score the full conversation and return verdict + breakdown."""
    import asyncio

    # Gap 1: auth check
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

    # Gap 6: graceful error on empty conversation
    if not conversation_history:
        return JSONResponse({
            "error": "no conversation to score",
            "final_score": 0.0,
            "hiring_result": {"decision": "No Hire", "confidence": "Low", "summary": "No interview data.", "panel_notes": []},
            "qa_history": [],
            "questions_score": {"score": 0, "notes": "No conversation provided."},
        }, status_code=200)

    # Gap 1: verify ownership against DB
    if session_id_val:
        try:
            cur = db_conn.cursor()
            db.execute(cur, "SELECT user_email FROM interview_sessions WHERE session_id=?", (session_id_val,))
            row = cur.fetchone()
            if row and row[0] and row[0].strip().lower() != session_email:
                return JSONResponse({"error": "forbidden"}, status_code=403)
        except Exception:
            pass  # Proceed if DB check fails (new sessions)

    # Extract candidate turns (skip warmup opener)
    candidate_turns = [t for t in conversation_history if t.get("speaker") == "candidate"]

    # Gap 5: wrap scoring in a timeout — if it exceeds 45s return partial results
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

    # Score questions-for-me
    q_score = {"score": 5, "notes": ""}
    if candidate_questions_text:
        try:
            q_score = await asyncio.to_thread(score_candidate_questions, candidate_questions_text, role, company)
        except Exception:
            pass

    # Final verdict
    total = sum(float(s.get("overall", s.get("score", 0))) for s in scored_timeline)
    count = max(1, len(scored_timeline))
    final_score = round(total / count, 1)
    hiring_result = hiring_decision(scored_timeline)
    hiring_result["curiosity_score"] = q_score

    # Save to DB
    if session_id_val:
        try:
            cur = db_conn.cursor()
            db.execute(cur,
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
        "partial": partial,  # Gap 5: flag to frontend if scoring was cut short
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
    selected_resume: str = Form(""),
    db_conn = Depends(db.get_conn),
):
    start = time.time()
    is_premium = is_premium_user(request)
    max_rounds = max(3, min(8, int(max_rounds)))
    if persona == "Pressure Test" and not is_premium:
        return templates.TemplateResponse(
            request=request,
            name="interview.html",
            context=interview_context_payload(request, premium_notice="Pressure Test mode is Premium only."),
        )
    if max_rounds > 3 and not is_premium:
        return templates.TemplateResponse(
            request=request,
            name="interview.html",
            context=interview_context_payload(request, premium_notice="More than 3 rounds requires Premium."),
        )
    user_email = (request.session.get("user_email") or "").strip().lower()

    if selected_resume:
        request.session["selected_resume_id"] = selected_resume.strip()

    resume_report, resume_context, resolved_role = resolve_resume_context(
        selected_resume or request.session.get("selected_resume_id", ""),
        user_email,
        request,
    )
    role = role.strip() or resolved_role or ""

    if user_email and (role.strip() or company.strip() or topic.strip()):
        prior_memory = get_user_memory(user_email)
        save_user_memory(
            user_email,
            target_role=role or prior_memory.get("target_role", ""),
            target_company=company or prior_memory.get("target_company", ""),
            focus_area=topic or prior_memory.get("focus_area", ""),
        )
    gaps = resume_report.get("keyword_gaps", []) if isinstance(resume_report, dict) else []
    skill_gaps = [str(g.get("keyword", "")).strip() for g in gaps if isinstance(g, dict) and g.get("keyword")]
    past_weaknesses = get_user_weaknesses(user_email) if user_email else []
    skill_gaps = list(set(skill_gaps + past_weaknesses))[:5]

    target_count = max(1, min(3, max_rounds))
    seeded = bank_questions(topic=topic, role=role, round_type=round_type, limit=target_count)
    questions = [normalize_question(q) for q in seeded if str(q).strip()]
    deduped = []
    seen = set()
    for q in questions:
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(q)
    questions = deduped[:target_count]
    if not questions:
        questions = [f"Tell me about your approach to {topic}."]

    session_id_val = str(uuid.uuid4())
    request.session["interview_id"] = session_id_val
    if user_email:
        cur = db_conn.cursor()
        now = int(time.time())
        db.execute(cur, "INSERT INTO interview_sessions (session_id, user_email, topic, difficulty, overall_score, qa_history_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (session_id_val, user_email, topic, difficulty, 0.0, "[]", now))
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

    return templates.TemplateResponse(request=request, name="interview.html", context=interview_context_payload(request))

@router.post("/evaluate", response_class=HTMLResponse)
def evaluate(request: Request,
             question: str = Form(...),
             answer: str = Form(...),
             answer_time_sec: float = Form(0.0),
             db_conn = Depends(db.get_conn)):
    start = time.time()

    # Prune session to avoid Cookes size limits (>4KB base64 overhead)
    request.session.pop("resume_versions", None)
    request.session.pop("audit_logs", None)
    
    questions = request.session.get("questions", [])
    ideal = request.session.get("ideal", [])
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
        except Exception as e:
            print(f"IDEAL GENERATION ERROR: {e}")
            ideal_answer = "Ideal answer unavailable. Explain your approach clearly with tradeoffs and impact."
        ideal_answer = normalize_question(ideal_answer)

        result = analyze_answer(
            question=question,
            answer=answer,
            ideal_answer=ideal_answer,
            round_type=str(config.get("round_type", "technical")),
            answer_time_sec=float(answer_time_sec or 0),
        )

        try:
            next_followup = future_followup.result(timeout=10)
        except Exception:
            next_followup = None

    print("SCORE:", result.get("overall"))
    print("======================\n")

    min_result = {
        "overall": result.get("overall", 0),
        "voice_pace": result.get("voice_pace", {})
    }
    timeline = timeline + [min_result]
    current += 1

    request.session["current"] = current
    request.session["timeline"] = timeline

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
    request.session["next_followup"] = next_followup

    finished = current >= max_rounds
    final_score = float(request.session.get("final_score", 0) or 0)
    hiring_result = request.session.get("hiring_result")

    if not finished:
        if not bool(config.get("fixed_questions", False)):
            user_email = (request.session.get("user_email") or "").strip().lower()
            resume_report = get_latest_resume_report_for_user(user_email) if user_email else {}
            resume_context = (resume_report.get("fixed_resume_md", "") or resume_report.get("resume_text", ""))[:2000] if resume_report else ""
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
                resume_context=resume_context,
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
                
            # Truncate past question contents in session buffer to shrink cookie size securely
            questions = list(questions)
            for idx in range(min(current, len(questions))):
                if isinstance(questions[idx], str) and len(questions[idx]) > 35:
                     questions[idx] = questions[idx][:32] + "..."
                     
            request.session["questions"] = questions
    else:
        full_timeline = []
        session_id_val = request.session.get("interview_id")
        if session_id_val:
            cur = db_conn.cursor()
            db.execute(cur, "SELECT qa_history_json FROM interview_sessions WHERE session_id=?", (session_id_val,))
            row = cur.fetchone()
            if row:
                try:
                    full_timeline = json.loads(row[0])
                except Exception:
                    full_timeline = []
            
            # Append current round to complete timeline detail before operations
            full_timeline.append({
                "round": len(timeline),
                "question": question,
                "user_answer": answer,
                "ideal_answer": ideal_answer,
                "score": result.get("overall", 0),
                "feedback": result.get("improvements", ["Solid performance"])[0] if result.get("improvements") else "Solid performance"
            })
        # Fallback to existing session timeline if DB load fails
        eval_timeline = full_timeline if full_timeline else timeline
        total = sum([float(s.get("overall", s.get("score", 0))) for s in eval_timeline])
        final_score = round(total / max(1, len(eval_timeline)), 1)
        hiring_result = hiring_decision(eval_timeline)
        request.session["final_score"] = final_score
        request.session["hiring_result"] = hiring_result
        request.session["finished"] = True
        current = max(0, min(current - 1, len(questions) - 1))
        request.session["current"] = current
        
    session_id_val = request.session.get("interview_id")
    if session_id_val:
        cur = db_conn.cursor()
        db.execute(cur, "SELECT qa_history_json FROM interview_sessions WHERE session_id=?", (session_id_val,))
        row = cur.fetchone()
        if row:
            try:
                hist = json.loads(row[0])
            except Exception:
                hist = []
            hist.append({
                "round": len(timeline),
                "question": question,
                "user_answer": answer,
                "ideal_answer": ideal_answer,
                "score": result.get("overall", 0),
                "feedback": result.get("improvements", ["Solid performance"])[0] if result.get("improvements") else "Solid performance"
            })
            if final_score is not None:
                cur = db_conn.cursor()
                db.execute(cur, "UPDATE interview_sessions SET qa_history_json=?, overall_score=? WHERE session_id=?", (json.dumps(hist), final_score, session_id_val))
            else:
                cur = db_conn.cursor()
                db.execute(cur, "UPDATE interview_sessions SET qa_history_json=? WHERE session_id=?", (json.dumps(hist), session_id_val))
            db_conn.commit()

        log_event(
            "interview_completed" if finished else "interview_progress",
            "mock_interview",
            role=str(config.get("role", "")),
            metadata={
                "topic": str(config.get("topic", "General")),
                "score": final_score,
                "decision": (hiring_result or {}).get("decision", ""),
            },
        )

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

    return templates.TemplateResponse(request=request, name="interview.html", context=interview_context_payload(
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
        log_event("honeypot_triggered", "mentorship", metadata={"ip": getattr(request.client, "host", "unknown")})
        return templates.TemplateResponse(request=request, name="book_call.html", context={"request": request, "error": "Request blocked.", "prefill": {}})
    start = time.time()

    safe_topic = re.sub(r'[^a-zA-Z0-9]+', '-', topic.strip()).strip('-') or 'session'
    room = f"mock-{safe_topic}-{int(time.time())}"
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
    log_model_health("mentorship_booking", "app_internal", success=True, latency_ms=(time.time() - start) * 1000.0)

    prefill = {"name": name, "email": email, "topic": topic, "outcome": outcome}
    return templates.TemplateResponse(
        request=request,
        name="book_call.html",
        context={
            "request": request,
            "prefill": prefill,
            "user_plan": current_user_plan(request),
            "user_role": request.session.get("user_role") or "user"
        }
    )


@router.post("/mindmap")
async def create_mindmap(request: Request, role: str = Form(...)):
    start = time.time()
    clean_role = (role or "").strip()

    # Pre-curated tracks cost 0 AI tokens and are free to explore without limit
    curated_keywords = ["python", "react", "frontend", "data scientist", "data science", "devops", "cloud architect"]
    is_curated = any(k in clean_role.lower() for k in curated_keywords)

    if not is_premium_user(request) and not is_curated:
        day_key = time.strftime("%Y-%m-%d")
        used_day = request.session.get("roadmap_day")
        used_count = int(request.session.get("roadmap_count", 0) or 0)
        if used_day != day_key:
            used_day = day_key
            used_count = 0
        if used_count >= 1:
            return JSONResponse(
                content={"error": "Free plan allows 1 custom AI roadmap/day. Upgrade for unlimited roadmaps.", "premium_required": True},
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
        from services.roadmap.mindmap_generator import get_curated_fallback
        fallback_data = get_curated_fallback(role)
        return JSONResponse(content=fallback_data, status_code=200)

@router.post("/skill-info")
async def skill_info(request: Request, skill: str = Form(...)):
    from services.roadmap.mindmap_generator import get_skill_info
    try:
        info = get_skill_info(skill)
        return JSONResponse(content=info, status_code=200)
    except Exception as e:
        print(f"Skill info error: {e}")
        return JSONResponse(content={
            "description": f"Core competency in {skill} is essential for engineering workflows.",
            "resources": [
                {"label": f"{skill} Documentation", "url": f"https://www.google.com/search?q={skill}+documentation"}
            ]
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


# ---------------------------------------------------------------------------
# Technology Cheatsheet & Resume Selection Endpoints
# ---------------------------------------------------------------------------
@router.get("/api/interview/resumes", response_class=JSONResponse)
def api_interview_resumes(request: Request):
    """Returns all available resumes for selection and the active selection."""
    try:
        user_email = (request.session.get("user_email") or "").strip().lower()
        resumes = get_selectable_resumes_for_user(user_email, request)
        selected_id = request.session.get("selected_resume_id", "")
        available_ids = [r["id"] for r in resumes]
        if selected_id not in available_ids:
            selected_id = available_ids[0] if available_ids else "latest"
        return JSONResponse({
            "resumes": resumes,
            "selected_resume_id": selected_id,
        })
    except Exception as e:
        logger.exception("api_interview_resumes failed: %s", e)
        return JSONResponse({"error": "Failed to load resumes. Please try again."}, status_code=500)


@router.post("/api/interview/select-resume", response_class=JSONResponse)
async def api_interview_select_resume(request: Request):
    """Switches the active resume context and re-tailors technologies and cheat sheets."""
    try:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

        resume_id = str(body.get("resume_id", "")).strip()
        if not resume_id:
            return JSONResponse({"error": "resume_id is required"}, status_code=400)

        user_email = (request.session.get("user_email") or "").strip().lower()
        selectable = get_selectable_resumes_for_user(user_email, request)
        available_ids = [r["id"] for r in selectable]

        if resume_id == "__upload__":
            return JSONResponse({"error": "Upload option selected, please upload a file"}, status_code=400)

        if resume_id not in available_ids:
            return JSONResponse({"error": "Selected resume not found"}, status_code=404)

        request.session["selected_resume_id"] = resume_id
        report, resume_text, target_role = resolve_resume_context(resume_id, user_email, request)

        resume_techs = extract_technologies_from_resume(resume_text, report)
        active_tech = resume_techs[0] if resume_techs else "FastAPI"

        cheatsheet = get_cheatsheet_for_technology(active_tech, resume_text=resume_text, target_role=target_role)

        saved_records = get_user_cheatsheets(user_email) if user_email else request.session.get("session_custom_cheatsheets", [])
        revised_indices = []
        for rec in saved_records:
            if rec.get("tech_name", "").lower() == active_tech.lower():
                revised_indices = rec.get("revised_indices", [])
                break
        if not revised_indices:
            revised_indices = request.session.get(f"revised_{active_tech.lower()}", [])
        cheatsheet["revised_indices"] = revised_indices

        return JSONResponse({
            "success": True,
            "selected_resume_id": resume_id,
            "target_role": target_role,
            "resume_technologies": resume_techs,
            "active_technology": active_tech,
            "cheatsheet": cheatsheet,
        })
    except Exception as e:
        logger.exception("api_interview_select_resume failed: %s", e)
        return JSONResponse({"error": f"Failed to switch resume: {e!s}"}, status_code=500)


@router.post("/api/interview/upload-resume", response_class=JSONResponse)
async def api_interview_upload_resume(
    request: Request,
    file: UploadFile = File(...),
    target_role: str = Form(""),
):
    """Uploads a new resume (PDF, TXT, TEX, MD), extracts text, sets it active, and returns tailored data."""
    try:
        filename = (file.filename or "uploaded_resume.pdf").strip()
        lower_name = filename.lower()

        content = await file.read()
        if not content:
            return JSONResponse({"error": "The uploaded file was empty. Please select a valid resume."}, status_code=400)

        text = ""
        resume_type = "pdf"
        if lower_name.endswith(".pdf"):
            resume_type = "pdf"
            try:
                from services.resume.resume_parser import extract_text
                text = extract_text(filename, content)
            except Exception as e:
                return JSONResponse({"error": f"Failed to parse PDF resume: {e!s}"}, status_code=400)
        elif lower_name.endswith((".tex", ".latex")):
            resume_type = "latex"
            try:
                raw_str = content.decode("utf-8", errors="ignore")
                from core.helpers import extract_text_from_latex
                text = extract_text_from_latex(raw_str)
            except Exception:
                text = content.decode("utf-8", errors="ignore")
        elif lower_name.endswith((".txt", ".md")):
            resume_type = "text"
            text = content.decode("utf-8", errors="ignore")
        else:
            return JSONResponse({"error": "Unsupported file format. Please upload a PDF, TXT, LaTeX, or Markdown file."}, status_code=400)

        if not text.strip():
            return JSONResponse({"error": "Could not extract readable text from the file. Please ensure it is not a scanned image."}, status_code=400)

        user_email = (request.session.get("user_email") or "").strip().lower()
        clean_title = filename.rsplit(".", 1)[0][:60]

        role = (target_role or "").strip()
        if not role:
            lowered = text.lower()
            if "data engineer" in lowered:
                role = "Data Engineer"
            elif "frontend" in lowered or "react" in lowered:
                role = "Frontend Developer"
            elif "backend" in lowered:
                role = "Backend Developer"
            elif "machine learning" in lowered or "data scientist" in lowered:
                role = "Machine Learning Engineer"
            elif "devops" in lowered or "cloud" in lowered:
                role = "DevOps Engineer"
            else:
                role = "Software Engineer"

        from core.database import save_user_resume
        new_saved_id = 0
        if user_email:
            try:
                new_saved_id = save_user_resume(
                    user_email=user_email,
                    title=clean_title,
                    resume_type=resume_type,
                    raw_content=text,
                    target_role=role,
                )
            except Exception as e:
                logger.warning("Failed to save user resume to db: %s", e)

        resume_id = f"saved_{new_saved_id}" if new_saved_id else f"uploaded_{uuid.uuid4().hex[:8]}"

        request.session["interview_uploaded_resume"] = {
            "id": resume_id,
            "title": clean_title,
            "text": text,
            "target_role": role,
        }
        request.session["selected_resume_id"] = resume_id

        resume_techs = extract_technologies_from_resume(text, {"resume_text": text, "target_role": role})
        active_tech = resume_techs[0] if resume_techs else "FastAPI"
        cheatsheet = get_cheatsheet_for_technology(active_tech, resume_text=text, target_role=role)

        selectable = get_selectable_resumes_for_user(user_email, request)

        return JSONResponse({
            "success": True,
            "selected_resume_id": resume_id,
            "title": clean_title,
            "target_role": role,
            "resumes": selectable,
            "resume_technologies": resume_techs,
            "active_technology": active_tech,
            "cheatsheet": cheatsheet,
        })
    except Exception as e:
        logger.exception("api_interview_upload_resume failed: %s", e)
        return JSONResponse({"error": f"Failed to upload resume: {e!s}"}, status_code=500)


@router.get("/api/interview/technologies", response_class=JSONResponse)
def api_interview_technologies(request: Request, resume_id: str = ""):
    """Returns detected resume technologies, saved custom technologies, and user role."""
    try:
        user_email = (request.session.get("user_email") or "").strip().lower()
        selected_id = resume_id.strip() or request.session.get("selected_resume_id", "")
        resume_report, resume_text, target_role = resolve_resume_context(selected_id, user_email, request)

        resume_techs = extract_technologies_from_resume(resume_text, resume_report)
        excluded = request.session.get("excluded_technologies", [])
        if excluded:
            resume_techs = [t for t in resume_techs if t.lower() not in [x.lower() for x in excluded]]

        saved_records = get_user_cheatsheets(user_email) if user_email else request.session.get("session_custom_cheatsheets", [])
        custom_techs = [c["tech_name"] for c in saved_records if isinstance(c, dict) and c.get("is_custom") and c.get("tech_name") and c["tech_name"].lower() not in [x.lower() for x in excluded]]
        saved_revised = {c["tech_name"]: c.get("revised_indices", []) for c in saved_records if isinstance(c, dict) and c.get("tech_name")}

        for tech in resume_techs:
            if tech not in saved_revised:
                session_revised = request.session.get(f"revised_{tech.lower()}", [])
                if session_revised:
                    saved_revised[tech] = session_revised

        return JSONResponse({
            "resume_technologies": resume_techs,
            "custom_technologies": custom_techs,
            "saved_revised": saved_revised,
            "target_role": target_role,
            "selected_resume_id": selected_id,
            "has_resume": bool(resume_text),
        })
    except Exception as e:
        logger.exception("api_interview_technologies failed: %s", e)
        return JSONResponse({"error": "Failed to load technologies. Please try again."}, status_code=500)


@router.get("/api/interview/cheatsheet", response_class=JSONResponse)
def api_interview_cheatsheet(request: Request, tech: str = "", resume_id: str = ""):
    """Returns the interview cheat sheet for a specific technology, tailored for the resume."""
    try:
        tech_name = tech.strip()
        if not tech_name:
            return JSONResponse({"error": "Technology name is required"}, status_code=400)

        user_email = (request.session.get("user_email") or "").strip().lower()
        selected_id = resume_id.strip() or request.session.get("selected_resume_id", "")
        resume_report, resume_text, target_role = resolve_resume_context(selected_id, user_email, request)

        saved_records = get_user_cheatsheets(user_email) if user_email else request.session.get("session_custom_cheatsheets", [])
        revised_indices = []
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

        if not revised_indices:
            revised_indices = request.session.get(f"revised_{tech_name.lower()}", [])

        if cached_payload:
            payload = cached_payload
        else:
            payload = get_cheatsheet_for_technology(tech_name, resume_text=resume_text, target_role=target_role)
            if user_email:
                save_user_cheatsheet(user_email, payload["tech_name"], payload, is_custom=False, revised_indices=revised_indices)
            else:
                session_custom = request.session.get("session_custom_cheatsheets", [])
                filtered = [c for c in session_custom if c.get("tech_name", "").lower() != payload["tech_name"].lower()]
                filtered.append({
                    "tech_name": payload["tech_name"],
                    "is_custom": False,
                    "revised_indices": revised_indices,
                    "cheatsheet": payload
                })
                request.session["session_custom_cheatsheets"] = filtered

        payload["revised_indices"] = revised_indices
        payload["selected_resume_id"] = selected_id
        return JSONResponse(payload)
    except Exception as e:
        logger.exception("api_interview_cheatsheet failed: %s", e)
        return JSONResponse({"error": f"Failed to load cheat sheet: {e!s}"}, status_code=500)


@router.post("/api/interview/cheatsheet/add", response_class=JSONResponse)
async def api_interview_cheatsheet_add(request: Request):
    """Adds a custom technology and generates its cheat sheet tailored to the candidate."""
    try:
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
            return JSONResponse({"error": f"Rate limit exceeded. Try again in {retry}s."}, status_code=429)
        record_auth_failure(request, "cheatsheet_add", identity=user_email or "anon", window_sec=300)

        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

        tech_name = str(body.get("tech", "")).strip()
        if not tech_name or len(tech_name) > 60:
            return JSONResponse({"error": "Technology name must be between 1 and 60 characters"}, status_code=400)

        clean_tech = re.sub(r"[^\w\s\.\+\#\-\/]", "", tech_name).strip()
        if not clean_tech:
            return JSONResponse({"error": "Invalid technology name"}, status_code=400)

        user_email = (request.session.get("user_email") or "").strip().lower()
        selected_id = str(body.get("resume_id", "")).strip() or request.session.get("selected_resume_id", "")
        resume_report, resume_text, target_role = resolve_resume_context(selected_id, user_email, request)

        payload = get_cheatsheet_for_technology(clean_tech, resume_text=resume_text, target_role=target_role)
        payload["revised_indices"] = []
        payload["selected_resume_id"] = selected_id

        # Re-enable if previously excluded
        excluded = request.session.get("excluded_technologies", [])
        if clean_tech.lower() in [x.lower() for x in excluded]:
            request.session["excluded_technologies"] = [x for x in excluded if x.lower() != clean_tech.lower()]

        if user_email:
            save_user_cheatsheet(user_email, payload["tech_name"], payload, is_custom=True, revised_indices=[])
        else:
            session_custom = request.session.get("session_custom_cheatsheets", [])
            filtered = [c for c in session_custom if c.get("tech_name", "").lower() != payload["tech_name"].lower()]
            filtered.append({
                "tech_name": payload["tech_name"],
                "is_custom": True,
                "revised_indices": [],
                "cheatsheet": payload,
            })
            request.session["session_custom_cheatsheets"] = filtered

        return JSONResponse(payload)
    except Exception as e:
        logger.exception("api_interview_cheatsheet_add failed: %s", e)
        return JSONResponse({"error": f"Failed to generate cheat sheet: {e!s}"}, status_code=500)


@router.post("/api/interview/cheatsheet/revise", response_class=JSONResponse)
async def api_interview_cheatsheet_revise(request: Request):
    """Updates revision status for a card in a technology cheat sheet."""
    try:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

        tech_name = str(body.get("tech", "")).strip()
        card_index = body.get("card_index")
        revised = bool(body.get("revised", True))

        if not tech_name or card_index is None:
            return JSONResponse({"error": "Technology name and card_index are required"}, status_code=400)

        try:
            idx = int(card_index)
        except (ValueError, TypeError):
            return JSONResponse({"error": "card_index must be an integer"}, status_code=400)

        user_email = (request.session.get("user_email") or "").strip().lower()

        if user_email:
            records = get_user_cheatsheets(user_email)
            curr_indices = []
            found = False
            for rec in records:
                if rec.get("tech_name", "").lower() == tech_name.lower():
                    curr_indices = list(rec.get("revised_indices", []))
                    found = True
                    break
            if revised:
                if idx not in curr_indices:
                    curr_indices.append(idx)
            else:
                if idx in curr_indices:
                    curr_indices.remove(idx)

            if found:
                update_cheatsheet_revised(user_email, tech_name, curr_indices)
            else:
                save_user_cheatsheet(user_email, tech_name, {}, is_custom=False, revised_indices=curr_indices)
        else:
            key = f"revised_{tech_name.lower()}"
            curr_indices = list(request.session.get(key, []))
            if revised:
                if idx not in curr_indices:
                    curr_indices.append(idx)
            else:
                if idx in curr_indices:
                    curr_indices.remove(idx)
            request.session[key] = curr_indices

        return JSONResponse({"success": True, "tech": tech_name, "revised_indices": curr_indices})
    except Exception as e:
        logger.exception("api_interview_cheatsheet_revise failed: %s", e)
        return JSONResponse({"error": f"Failed to update revision status: {e!s}"}, status_code=500)


@router.delete("/api/interview/cheatsheet", response_class=JSONResponse)
def api_interview_cheatsheet_delete(request: Request, tech: str = ""):
    """Removes a custom or resume technology from the candidate's list."""
    try:
        tech_name = tech.strip()
        if not tech_name:
            return JSONResponse({"error": "Technology name is required"}, status_code=400)

        user_email = (request.session.get("user_email") or "").strip().lower()
        if user_email:
            delete_user_cheatsheet(user_email, tech_name)
        else:
            session_custom = request.session.get("session_custom_cheatsheets", [])
            session_custom = [c for c in session_custom if c.get("tech_name", "").lower() != tech_name.lower()]
            request.session["session_custom_cheatsheets"] = session_custom

        excluded = request.session.get("excluded_technologies", [])
        if tech_name.lower() not in [x.lower() for x in excluded]:
            excluded.append(tech_name)
            request.session["excluded_technologies"] = excluded

        return JSONResponse({"success": True, "deleted": tech_name})
    except Exception as e:
        logger.exception("api_interview_cheatsheet_delete failed: %s", e)
        return JSONResponse({"error": f"Failed to delete technology: {e!s}"}, status_code=500)


@router.get("/interview/cheatsheet/export", response_class=HTMLResponse)
def interview_cheatsheet_export(request: Request, tech: str = "FastAPI"):
    """Downloads a standalone, fully offline-compatible HTML cheat sheet matching the user specification."""
    try:
        tech_name = tech.strip() or "FastAPI"
        user_email = (request.session.get("user_email") or "").strip().lower()
        resume_report = get_latest_resume_report_for_user(user_email) if user_email else request.session.get("last_resume_report", {})
        resume_text = (resume_report or {}).get("resume_text", "") or (resume_report or {}).get("fixed_resume_md", "")
        target_role = (resume_report or {}).get("target_role", "") or (get_user_memory(user_email) if user_email else {}).get("target_role", "") or "Software Engineer"

        cheatsheet = get_cheatsheet_for_technology(tech_name, resume_text=resume_text, target_role=target_role)
        html_content = build_standalone_cheatsheet_html(
            tech_name=cheatsheet["tech_name"],
            cards=cheatsheet["cards"],
            target_role=target_role,
        )
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", cheatsheet["tech_name"].lower()).strip("_")
        headers = {"Content-Disposition": f'attachment; filename="{slug}_interview_cheatsheet.html"'}
        return HTMLResponse(content=html_content, headers=headers)
    except Exception as e:
        logger.exception("interview_cheatsheet_export failed: %s", e)
        return HTMLResponse(content=f"<html><body><h1>Export Error</h1><p>{e!s}</p></body></html>", status_code=500)
