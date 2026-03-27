import json
import time
from typing import List, Optional, Dict
from fastapi import Request
from features.shared import call_ai_with_fallback, call_ai_chat
from db import current_user_plan, get_user_memory
from .personas import PERSONA_SYSTEM_PROMPTS, DEFAULT_PERSONA

def generate_interviewer_response(
    conversation_history: list[dict],
    config: dict,
    persona: str = "Neutral",
    phase: str = "interview",
) -> str:
    persona_prompt = PERSONA_SYSTEM_PROMPTS.get(persona, DEFAULT_PERSONA)
    role = config.get("role", "Software Engineer")
    company = config.get("company", "a tech company")
    topic = config.get("topic", "general technical topics")
    round_type = config.get("round_type", "technical")
    skill_gaps = config.get("skill_gaps", [])
    resume_context = config.get("resume_context", "")
    max_rounds = int(config.get("max_rounds", 5))

    system_content = f"""{persona_prompt}

Context for this session:
- Candidate is interviewing for: {role} at {company}
- Interview topic: {topic}
- Round type: {round_type}
- Number of topics to cover: {max_rounds}
- Skill gaps: {", ".join(skill_gaps) if skill_gaps else "general depth"}
- Resume highlights: {resume_context[:1000] if resume_context else "not provided"}

Current phase: {phase}
{"If phase is 'closing', wrap up with: 'That's all the questions I have. Before we finish — do you have any questions for me?'" if phase == "closing" else ""}
{"If phase is 'questions_for_me', answer the candidate's questions naturally, then close the session." if phase == "questions_for_me" else ""}

Keep your response concise and natural. Speak exactly as a real interviewer would."""

    messages = [{"role": "system", "content": system_content}]
    for turn in conversation_history:
        role_tag = "assistant" if turn["speaker"] == "interviewer" else "user"
        messages.append({"role": role_tag, "content": turn["text"]})

    try:
        return call_ai_chat(messages=messages, temperature=0.6, max_tokens=300)
    except Exception:
        if phase == "closing": return "That's all the questions I have. Do you have any questions for me?"
        if phase == "questions_for_me": return "Great. Thanks for your time today. You'll hear back from us soon."
        return "Can you go deeper on that? Walk me through a specific example."

def generate_opener(config: dict, persona: str = "Neutral") -> str:
    role = config.get("role", "Software Engineer")
    company = config.get("company", "our company")
    round_type = config.get("round_type", "technical")
    persona_names = {"Friendly": "Jordan", "Neutral": "Alex", "Pressure Test": "Morgan"}
    interviewer_name = persona_names.get(persona, "Alex")

    if persona == "Friendly":
        return f"Hi! Thanks so much for joining us. I'm {interviewer_name} — I'll be conducting your {round_type} interview for the {role} role at {company}. We have about 45 minutes together. To kick things off — can you give me a quick overview of your background?"
    elif persona == "Pressure Test":
        return f"Let's get started. I'm {interviewer_name}, conducting your {round_type} interview for {role}. We'll cover a few technical areas — I'll go deep and I'll push back. First: give me a 90-second summary of your background. Be specific."
    else:
        return f"Hi, thanks for joining. I'm {interviewer_name} — I'll be running your {round_type} interview for {role} at {company}. Before we get into technical questions — can you give me a brief overview of your background?"

def generate_questions(topic: str, role: str = "", company: str = "", round_type: str = "technical", difficulty: str = "intermediate", persona: str = "Neutral", skill_gaps: Optional[List[str]] = None, num_questions: int = 1, resume_context: str = "") -> list[str]:
    prompt = f"Create {num_questions} interview questions for {topic} ({difficulty}) for a {role} at {company}. Persona: {persona}. Skill Gaps: {skill_gaps}. Resume: {resume_context}. JSON only: {{\"questions\":[\"...\"]}}"
    try:
        parsed = call_ai_with_fallback(prompt, "", temperature=0.3)
        questions = parsed.get("questions", [])
        if isinstance(questions, list) and questions: return [str(q).strip() for q in questions if str(q).strip()]
    except Exception: pass
    return [f"Explain a core {topic} concept and how you would apply it in a {role} role."]

def generate_follow_up(question: str, answer: str, topic: str, role: str = "", round_type: str = "technical", persona: str = "Neutral") -> str:
    prompt = f"Create a follow-up for: Q: {question} A: {answer}. Topic: {topic}. Persona: {persona}. JSON only: {{\"follow_up\":\"...\"}}"
    try:
        parsed = call_ai_with_fallback(prompt, "", temperature=0.2)
        follow_up = str(parsed.get("follow_up", "")).strip()
        if follow_up: return follow_up
    except Exception: pass
    return "Can you go deeper with one concrete example and measurable impact?"

def generate_lifeline_hints(question: str, resume_context: str = "") -> list[str]:
    prompt = f"The candidate is stuck on: \"{question}\". Provide 3 hints based on: {resume_context}. JSON only: {{\"hints\": [\"...\", \"...\", \"...\"]}}"
    try:
        parsed = call_ai_with_fallback(prompt, "", temperature=0.4)
        hints = parsed.get("hints", [])
        if isinstance(hints, list) and hints: return [str(h) for h in hints[:3]]
    except Exception: pass
    return ["Recall a specific project where you faced a similar challenge.", "Use the STAR method.", "Highlight measurable impact or metrics."]

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
    timeline = request.session.get("timeline", [])
    user_email = (request.session.get("user_email") or "").strip().lower()
    memory = get_user_memory(user_email)
    config = request.session.get("interview_config", {}) or {}
    default_setup = {
        "topic": memory.get("focus_area", "") or "Python",
        "role": memory.get("target_role", ""),
        "company": memory.get("target_company", ""),
    }
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
    }
    payload.update(extra)
    return payload
