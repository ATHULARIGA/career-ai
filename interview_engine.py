import json
import os
from typing import Any, List, Optional

from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENAI_API_KEY"),
)


def _parse_json(raw: str) -> dict[str, Any]:
    cleaned = (raw or "").replace("```json", "").replace("```", "").strip()
    if "{" in cleaned and "}" in cleaned:
        cleaned = cleaned[cleaned.find("{"):cleaned.rfind("}") + 1]
    return json.loads(cleaned)


def _fallback_questions(topic: str, difficulty: str, persona: str, n: int) -> list[str]:
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
) -> list[str]:
    skill_gaps = skill_gaps or []
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

Rules:
- Keep each question clear, concise, and realistic.
- If persona is "Pressure Test", make the wording sharper, more probing, and deeply skeptical to stress-test the candidate.
- If persona is "Friendly", be warm and encouraging in the phrasing.
- If round type is behavioral, prioritize STAR-style scenarios.
- Return JSON only in this exact format:
{{"questions":["..."]}}
"""
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        parsed = _parse_json(response.choices[0].message.content)
        questions = parsed.get("questions", [])
        if isinstance(questions, list):
            cleaned = [str(q).strip() for q in questions if str(q).strip()]
            if cleaned:
                return cleaned[:num_questions]
    except Exception as e:
        print(f"QUESTION GEN ERROR: {e}")

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
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        parsed = _parse_json(response.choices[0].message.content)
        follow_up = str(parsed.get("follow_up", "")).strip()
        if follow_up:
            return follow_up
    except Exception as e:
        print(f"FOLLOW UP ERROR: {e}")

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
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            temperature=0.4,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        parsed = _parse_json(response.choices[0].message.content)
        hints = parsed.get("hints", [])
        if isinstance(hints, list) and len(hints) > 0:
            return [str(h) for h in hints[:3]]
    except Exception as e:
        print(f"LIFELINE ERROR: {e}")

    return [
        "Recall a specific project where you faced a similar challenge.",
        "Use the STAR method: Situation, Task, Action, Result.",
        "Highlight measurable impact or metrics if possible."
    ]
