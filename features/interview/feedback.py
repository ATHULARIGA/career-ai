import re
import logging
from typing import Any
from .grader import grade_answer
from features.shared import call_ai_with_fallback, clamp_score

logger = logging.getLogger("resumate")

FILLERS = {
    "um", "uh", "like", "you know", "actually", "basically", "literally",
    "sort of", "kind of", "i mean",
}

def _contains_any(text: str, needles: list[str]) -> bool:
    lower = text.lower()
    return any(n in lower for n in needles)

def _star_coach(answer: str) -> dict[str, Any]:
    lower = answer.lower()
    has_s = _contains_any(lower, ["situation", "context", "at my previous", "when i was"])
    has_t = _contains_any(lower, ["task", "goal", "objective", "responsible"])
    has_a = _contains_any(lower, ["i did", "i built", "i implemented", "i designed", "i led"])
    has_r = _contains_any(lower, ["result", "%", "increased", "reduced", "improved", "saved"])
    missing = []
    if not has_s: missing.append("Situation")
    if not has_t: missing.append("Task")
    if not has_a: missing.append("Action")
    if not has_r: missing.append("Result")
    return {
        "present": {"Situation": has_s, "Task": has_t, "Action": has_a, "Result": has_r},
        "missing": missing,
        "tip": "Use STAR: 1 sentence context, 1 sentence goal, 2-3 action steps, 1 measurable result.",
    }

def analyze_answer(
    question: str,
    answer: str,
    ideal_answer: str,
    round_type: str = "technical",
    answer_time_sec: float = 0.0,
) -> dict[str, Any]:
    answer = (answer or "").strip()
    words = re.findall(r"\b\w+\b", answer)
    word_count = len(words)
    sentence_count = max(1, len([s for s in re.split(r"[.!?]+", answer) if s.strip()]))
    avg_sentence_len = word_count / sentence_count
    numeric_hits = len(re.findall(r"\d+%?|\$?\d+", answer))

    correctness = grade_answer(answer, ideal_answer).get("correctness", 0.0)

    filler_hits = 0
    lower = answer.lower()
    for f in FILLERS:
        filler_hits += lower.count(f)
    filler_density = (filler_hits / max(1, word_count)) * 100

    wpm = (word_count / answer_time_sec) * 60.0 if answer_time_sec > 0 else 0.0

    if 60 <= word_count <= 150: structure_score = 10.0
    elif word_count < 60: structure_score = clamp_score((word_count / 60) * 10)
    else: structure_score = clamp_score(10 - ((word_count - 150) / 30))

    clarity_score = clamp_score(10 - max(0, abs(18 - avg_sentence_len) * 0.4))
    depth_score = clamp_score((correctness * 0.65) + min(3.0, word_count / 35))
    impact_score = clamp_score(min(10, 4 + numeric_hits * 2))
    confidence_score = clamp_score(10 - filler_density * 1.8)
    communication_score = clamp_score((clarity_score * 0.6) + (confidence_score * 0.4))

    star = _star_coach(answer) if round_type == "behavioral" else {"present": {}, "missing": [], "tip": "Use structure: context, approach, tradeoffs, results."}

    pacing_band = "Unknown"
    if wpm > 0:
        if wpm < 30: pacing_band = "Too slow"
        elif wpm <= 80: pacing_band = "Good pace"
        elif wpm <= 120: pacing_band = "Fast"
        else: pacing_band = "Suspiciously fast"

    rubric = {
        "correctness": clamp_score(correctness), "structure": structure_score,
        "clarity": clarity_score, "technical_depth": depth_score,
        "impact": impact_score, "communication": communication_score,
    }
    overall = clamp_score(sum(rubric.values()) / len(rubric))

    return {
        "rubric": rubric, "overall": overall,
        "strengths": ["Semantically aligned", "Clear structure", "Solid depth"][:3],
        "improvements": ["Increase technical specificity", "Add metrics"][:4],
        "voice_pace": {
            "answer_time_sec": round(answer_time_sec, 1), "word_count": word_count,
            "wpm": round(wpm, 1), "pace_band": pacing_band, "filler_hits": filler_hits,
        },
        "star_coach": star, "question": question,
    }

def hiring_decision(session_history: list[dict[str, Any]]) -> dict[str, Any]:
    if not session_history:
        return {"decision": "No Hire", "confidence": "Low", "summary": "Not enough data.", "panel_notes": []}

    avg = sum(float(item.get("overall", 0)) for item in session_history) / len(session_history)
    decision = "Strong Hire" if avg >= 8 else "Lean Hire" if avg >= 6.5 else "Borderline" if avg >= 5 else "No Hire"
    
    return {
        "decision": decision, "confidence": "Medium",
        "summary": "Simulated result based on rubric.",
        "panel_notes": [f"Average rubric score: {round(avg, 1)}/10."],
    }

def score_candidate_questions(candidate_questions_text: str, role: str, company: str) -> dict:
    prompt = f"Score candidate questions for {role} at {company}: {candidate_questions_text}. JSON only: {{\"score\": 0, \"notes\": \"\"}}"
    try:
        parsed = call_ai_with_fallback(prompt, "", temperature=0.2, max_tokens=100)
        return {"score": int(parsed.get("score", 5)), "notes": str(parsed.get("notes", ""))}
    except Exception:
        return {"score": 5, "notes": "Candidate asked questions."}
