from fastapi import APIRouter, Request, Form, UploadFile, File, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse
import uuid
import json
from core import *
from ideal_generator import generate_ideal_answer
from interview_engine import (
    generate_interviewer_response,
    generate_opener,
    score_candidate_questions,
)
from interview_feedback import analyze_answer, hiring_decision

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

import db_backend as db


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
def _trim_history(history: list, keep_recent: int = 9) -> list:
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
        import time
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
                time.sleep(0.1)

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
        if key in seen:
            continue
        seen.add(key)
        deduped.append(q)
    questions = deduped[: max(1, min(3, max_rounds))]
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

    with open("/tmp/evaluate_debug.log", "a") as f:
        f.write(f"--- DEBUG EVALUATE ---\n")
        f.write(f"current: {current}\n")
        f.write(f"max_rounds: {max_rounds}\n")
        f.write(f"questions_len: {len(questions)}\n")
        f.write(f"finished: {finished}\n")
        f.write(f"questions: {questions}\n")
        try:
            payload_ser = json.dumps(dict(request.session))
            f.write(f"SESSION SIZE: {len(payload_ser)} bytes\n")
            f.write(f"SESSION: {payload_ser}\n")
        except Exception as e:
            f.write(f"SESSION DUMP ERR: {e}\n")
        f.write(f"----------------------\n")

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
