import json
import os
from typing import Any, List, Optional

from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENAI_API_KEY"),
)

# ---------------------------------------------------------------------------
# Per-Persona System Prompts — define full behavioral personality, not just tone
# ---------------------------------------------------------------------------

PERSONA_SYSTEM_PROMPTS = {
    "Friendly": """You are a warm, encouraging interviewer conducting a technical interview.
Your behavioral rules:
- Begin with a genuine, welcoming opener. Use the candidate's name when known.
- When the candidate gives a partial answer, validate what's correct and prompt them to extend it: "That's a good start — can you extend that to handle X?"
- If the candidate stalls for a moment, prompt gently: "Take your time — what comes to mind first?"
- Ask follow-up questions that build on what the candidate already said, referencing specifics they mentioned.
- Wrap up each topic naturally: "Great, let's move to the next area when you're ready."
- Never be harsh or dismissive. Always leave the candidate feeling heard.
- Keep your replies conversational and concise — max 2-3 sentences per turn unless explaining something.""",

    "Neutral": """You are a professional, neutral interviewer conducting a structured technical interview.
Your behavioral rules:
- Keep responses short and direct. No praise, no criticism.
- When the candidate finishes, acknowledge briefly and move on: "Got it." or "Understood. Let's continue."
- If the candidate stalls, stay silent — do not offer prompts. Just wait. If they explicitly ask for a hint, offer one short clarifying question.
- Ask one follow-up per topic to test depth, then move on.
- Do not reference emotions or effort. Evaluate content only.
- Keep your replies under 2 sentences unless asking a multi-part question.""",

    "Pressure Test": """You are a tough, skeptical senior interviewer who stress-tests candidates rigorously.
Your behavioral rules:
- Never validate correct answers — always probe deeper, even when they're right.
- Challenge every metric the candidate claims: "How did you actually measure that?" or "40% improvement by what baseline?"
- Show mild skepticism in your phrasing: "That sounds like a textbook answer. What actually went wrong in production?"
- If the candidate gives a long answer, interrupt: "Stop — summarise that in one sentence."
- Ask sharp follow-ups that expose gaps: edge cases, failure modes, alternatives you didn't consider.
- Never say "good" or "interesting". Stay cold and probing.
- Keep replies short and crisp — pressure comes from brevity and directness.""",
}

DEFAULT_PERSONA = PERSONA_SYSTEM_PROMPTS["Neutral"]

INTERVIEW_MODELS = ["openai/gpt-4o-mini", "meta-llama/llama-3.1-8b-instruct", "google/gemma-2-9b-it"]

# ---------------------------------------------------------------------------
# Conversational interview engine
# ---------------------------------------------------------------------------

def generate_interviewer_response(
    conversation_history: list[dict],
    config: dict,
    persona: str = "Neutral",
    phase: str = "interview",
) -> str:
    """
    Generate the next interviewer message given the full conversation thread.
    conversation_history: list of {"speaker": "interviewer"|"candidate", "text": str}
    phase: "warmup" | "interview" | "closing" | "questions_for_me"
    """
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
- Skill gaps to probe (from resume analysis): {", ".join(skill_gaps) if skill_gaps else "general depth"}
- Resume highlights: {resume_context[:1000] if resume_context else "not provided"}

Current phase: {phase}
{"If phase is 'closing', wrap up with: 'That's all the questions I have. Before we finish — do you have any questions for me about the role or the team?'" if phase == "closing" else ""}
{"If phase is 'questions_for_me', answer the candidate's questions naturally as an interviewer would, then close the session with a polite goodbye." if phase == "questions_for_me" else ""}

Important: Keep your response concise and natural. Do NOT number your questions. Do NOT explain what you're grading. Speak exactly as a real interviewer would in a live conversation."""

    messages = [{"role": "system", "content": system_content}]

    for turn in conversation_history:
        if turn["speaker"] == "interviewer":
            messages.append({"role": "assistant", "content": turn["text"]})
        else:
            messages.append({"role": "user", "content": turn["text"]})

    for model in INTERVIEW_MODELS:
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0.6,
                max_tokens=300,
                messages=messages,
            )
            reply = (response.choices[0].message.content or "").strip()
            if reply:
                return reply
        except Exception as e:
            print(f"CHAT GEN ERROR using {model}: {e}")

    # Fallback
    if phase == "closing":
        return "That's all the questions I have. Before we wrap up — do you have any questions for me about the role or the team?"
    if phase == "questions_for_me":
        return "Great. Thanks for your time today — you'll hear back from us within a few days. Have a good rest of your day."
    return "Can you go deeper on that? Walk me through a specific example."


def generate_opener(config: dict, persona: str = "Neutral") -> str:
    """Generate the structured interview intro + opener question."""
    role = config.get("role", "Software Engineer")
    company = config.get("company", "our company")
    round_type = config.get("round_type", "technical")
    persona_names = {
        "Friendly": "Jordan",
        "Neutral": "Alex",
        "Pressure Test": "Morgan",
    }
    interviewer_name = persona_names.get(persona, "Alex")

    if persona == "Friendly":
        intro = (
            f"Hi! Thanks so much for joining us today. I'm {interviewer_name} — I'll be conducting your "
            f"{round_type} interview for the {role} role at {company}. "
            f"We have about 45 minutes together. I'll start with a quick intro question to warm up, "
            f"then we'll move through a few technical areas, and leave some time at the end for your questions. Sound good? "
            f"\n\nTo kick things off — can you give me a quick 2-minute overview of your background and what you're currently working on?"
        )
    elif persona == "Pressure Test":
        intro = (
            f"Let's get started. I'm {interviewer_name}, conducting your {round_type} interview for {role}. "
            f"We'll cover a few technical areas — I'll go deep and I'll push back, so expect that. "
            f"\n\nFirst: give me a 90-second summary of your background. Be specific."
        )
    else:
        intro = (
            f"Hi, thanks for joining. I'm {interviewer_name} — I'll be running your {round_type} interview "
            f"for the {role} position at {company}. "
            f"We'll work through a few topics today and leave time at the end for your questions. "
            f"\n\nBefore we get into the technical questions — can you give me a brief overview of your background and what you're currently focused on?"
        )
    return intro


def score_candidate_questions(candidate_questions_text: str, role: str, company: str) -> dict:
    """
    Score the candidate's 'questions for the interviewer' segment.
    Returns: {"score": 0-10, "notes": str}
    """
    prompt = f"""
A candidate is interviewing for {role} at {company}.
At the end of the interview they were asked "Do you have any questions for me?"

Their response: "{candidate_questions_text}"

Score their response from 0-10 based on:
- 0-3: No questions asked, or purely logistical questions (salary, hours)
- 4-6: Generic questions (team culture, tech stack) that show basic interest
- 7-9: Specific, informed questions about the role, company challenges, or team
- 10: Exceptional — demonstrates deep research, asks about strategy, roadmap, or engineering challenges specific to the company

Return JSON only:
{{"score": <int 0-10>, "notes": "<one sentence explanation>"}}
"""
    for model in INTERVIEW_MODELS:
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0.2,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )
            parsed = _parse_json(response.choices[0].message.content)
            score = int(parsed.get("score", 5))
            notes = str(parsed.get("notes", "")).strip()
            return {"score": score, "notes": notes}
        except Exception as e:
            print(f"QUESTION SCORE ERROR using {model}: {e}")

    return {"score": 5, "notes": "Candidate asked questions at the end of the interview."}


def _parse_json(raw: str) -> dict[str, Any]:
    cleaned = (raw or "").replace("```json", "").replace("```", "").strip()
    if "{" in cleaned and "}" in cleaned:
        cleaned = cleaned[cleaned.find("{"):cleaned.rfind("}") + 1]
    return json.loads(cleaned)


def _fallback_questions(topic: str, difficulty: str, persona: str, n: int) -> list[str]:
    n = max(1, min(n, 7))
    base = [
        f"Explain a core {topic} concept and how you would teach it to a new teammate.",
        f"Describe a difficult {topic} problem you solved and the tradeoffs you made.",
        f"How would you test and monitor a {topic} solution in production?",
        f"What are common failure modes in {topic}, and how would you mitigate them?",
        f"Tell me about a project where {topic} decisions affected performance or scalability.",
    ]
    if difficulty == "advanced":
        base = [f"[Advanced] {q}" for q in base]
    if persona == "Pressure Test":
        base = [f"[Pressure Test] {q}" for q in base]
    return base[:n]


def generate_questions(
    topic: str,
    role: str = "",
    company: str = "",
    round_type: str = "technical",
    difficulty: str = "intermediate",
    persona: str = "Neutral",
    skill_gaps: Optional[List[str]] = None,
    num_questions: int = 1,
    resume_context: str = "",
) -> list[str]:
    skill_gaps = skill_gaps or []
    num_questions = max(1, min(num_questions, 7))
    prompt = f"""
You are an expert interviewer.
Create {num_questions} interview question(s) with this context:
- Topic: {topic}
- Role: {role or "General"}
- Company style: {company or "General tech company"}
- Round type: {round_type}
- Difficulty: {difficulty}
- Interviewer Persona: {persona}
- Focus skill gaps: {", ".join(skill_gaps) if skill_gaps else "None"}
- Candidate resume highlights: {resume_context or "Not provided"}

Rules:
- Keep each question clear, concise, and realistic.
- If resume is provided, reference specific projects or claims in the questions.
- If persona is "Pressure Test", make the wording sharper, more probing, and deeply skeptical to stress-test the candidate.
- If persona is "Friendly", be warm and encouraging in the phrasing.
- If round type is behavioral, prioritize STAR-style scenarios.
- Return JSON only in this exact format:
{{"questions":["..."]}}
"""
    models = ["openai/gpt-4o-mini", "meta-llama/llama-3.1-8b-instruct", "google/gemma-2-9b-it"]
    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            parsed = _parse_json(response.choices[0].message.content)
            questions = parsed.get("questions", [])
            if isinstance(questions, list):
                cleaned = [str(q).strip() for q in questions if str(q).strip()]
                if cleaned:
                    return cleaned[:num_questions]
        except Exception as e:
            print(f"QUESTION GEN ERROR using {model}: {e}")

    return _fallback_questions(topic, difficulty, persona, num_questions)


def generate_follow_up(
    question: str,
    answer: str,
    topic: str,
    role: str = "",
    round_type: str = "technical",
    persona: str = "Neutral",
) -> str:
    prompt = f"""
Create one high-value follow-up interview question based on:
- Original question: {question}
- Candidate answer: {answer}
- Topic: {topic}
- Role: {role or "General"}
- Round type: {round_type}
- Interviewer Persona: {persona} (If Pressure Test: interrupt the flow, be highly skeptical of their claims, demand metrics, act like a tough interviewer. If Friendly: encourage their train of thought.)

Return JSON only:
{{"follow_up":"..."}}
"""
    models = ["openai/gpt-4o-mini", "meta-llama/llama-3.1-8b-instruct", "google/gemma-2-9b-it"]
    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            parsed = _parse_json(response.choices[0].message.content)
            follow_up = str(parsed.get("follow_up", "")).strip()
            if follow_up:
                return follow_up
        except Exception as e:
            print(f"FOLLOW UP ERROR using {model}: {e}")

    if persona == "Pressure Test":
        return "Your answer seems broad. Defend one design choice with concrete metrics and tradeoffs."
    return "Can you go deeper with one concrete example and measurable impact?"

def generate_lifeline_hints(question: str, resume_context: str = "") -> list[str]:
    prompt = f"""
The candidate is stuck on this interview question:
"{question}"

Their resume summary/highlights for context:
{resume_context or "No resume provided."}

Provide exactly 3 short, punchy bullet points to jog their memory and help them structure their answer. 
Draft these hints using their resume data if available, or general best practices if not.
Return JSON only:
{{"hints": ["Hint 1", "Hint 2", "Hint 3"]}}
"""
    models = ["openai/gpt-4o-mini", "meta-llama/llama-3.1-8b-instruct", "google/gemma-2-9b-it"]
    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0.4,
                messages=[{"role": "user", "content": prompt}],
            )
            parsed = _parse_json(response.choices[0].message.content)
            hints = parsed.get("hints", [])
            if isinstance(hints, list) and len(hints) > 0:
                return [str(h) for h in hints[:3]]
        except Exception as e:
            print(f"LIFELINE ERROR using {model}: {e}")

    return [
        "Recall a specific project where you faced a similar challenge.",
        "Use the STAR method: Situation, Task, Action, Result.",
        "Highlight measurable impact or metrics if possible."
    ]
