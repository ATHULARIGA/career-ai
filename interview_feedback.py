import re
from typing import Any

from grader import grade_answer

FILLERS = {
    "um", "uh", "like", "you know", "actually", "basically", "literally",
    "sort of", "kind of", "i mean",
}


def _clamp(n: float, lo: float = 0.0, hi: float = 10.0) -> float:
    return round(max(lo, min(hi, n)), 1)


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
    if not has_s:
        missing.append("Situation")
    if not has_t:
        missing.append("Task")
    if not has_a:
        missing.append("Action")
    if not has_r:
        missing.append("Result")
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

    wpm = 0.0
    if answer_time_sec and answer_time_sec > 0:
        wpm = (word_count / answer_time_sec) * 60.0

    structure_score = _clamp((word_count / 45) * 10)
    clarity_score = _clamp(10 - max(0, abs(18 - avg_sentence_len) * 0.4))
    depth_score = _clamp((correctness * 0.65) + min(3.0, word_count / 35))
    impact_score = _clamp(min(10, 4 + numeric_hits * 2))
    confidence_score = _clamp(10 - filler_density * 1.8)
    communication_score = _clamp((clarity_score * 0.6) + (confidence_score * 0.4))

    star = _star_coach(answer)
    if round_type != "behavioral":
        star["tip"] = "Use structure: concise context, technical approach, tradeoffs, measurable result."

    pacing_band = "Unknown"
    if wpm > 0:
        if wpm < 90:
            pacing_band = "Too slow"
        elif wpm <= 165:
            pacing_band = "Balanced"
        else:
            pacing_band = "Too fast"

    rubric = {
        "correctness": _clamp(correctness),
        "structure": structure_score,
        "clarity": clarity_score,
        "technical_depth": depth_score,
        "impact": impact_score,
        "communication": communication_score,
    }
    overall = _clamp(sum(rubric.values()) / len(rubric))

    strengths = []
    if rubric["correctness"] >= 7:
        strengths.append("Answer was semantically aligned with expected content.")
    if numeric_hits > 0:
        strengths.append("Included measurable evidence.")
    if rubric["clarity"] >= 7:
        strengths.append("Response was easy to follow.")

    improvements = []
    if rubric["correctness"] < 6:
        improvements.append("Increase technical accuracy and specificity.")
    if numeric_hits == 0:
        improvements.append("Add metrics to demonstrate real impact.")
    if filler_density > 2:
        improvements.append("Reduce filler words to sound more confident.")
    if word_count < 35:
        improvements.append("Provide a deeper answer with approach and tradeoffs.")

    return {
        "rubric": rubric,
        "overall": overall,
        "strengths": strengths[:3],
        "improvements": improvements[:4],
        "voice_pace": {
            "answer_time_sec": round(answer_time_sec, 1),
            "word_count": word_count,
            "wpm": round(wpm, 1),
            "pace_band": pacing_band,
            "filler_hits": filler_hits,
            "filler_density_pct": round(filler_density, 2),
        },
        "star_coach": star,
        "question": question,
        "answer_preview": answer[:280],
    }


def hiring_decision(session_history: list[dict[str, Any]]) -> dict[str, Any]:
    if not session_history:
        return {
            "decision": "No Hire",
            "confidence": "Low",
            "summary": "Not enough data.",
            "panel_notes": [],
        }

    overall_scores = [float(item.get("overall", 0)) for item in session_history]
    avg = sum(overall_scores) / len(overall_scores)
    if avg >= 8:
        decision = "Strong Hire"
        confidence = "High"
    elif avg >= 6.5:
        decision = "Lean Hire"
        confidence = "Medium"
    elif avg >= 5:
        decision = "Borderline"
        confidence = "Medium"
    else:
        decision = "No Hire"
        confidence = "High"

    panel_notes = []
    last = session_history[-1]
    strengths = last.get("strengths", [])
    improvements = last.get("improvements", [])
    if strengths:
        panel_notes.append(f"Recent strength: {strengths[0]}")
    if improvements:
        panel_notes.append(f"Main concern: {improvements[0]}")
    panel_notes.append(f"Average rubric score across session: {round(avg, 1)}/10.")

    return {
        "decision": decision,
        "confidence": confidence,
        "summary": "Simulated hiring panel outcome based on rubric and consistency.",
        "panel_notes": panel_notes,
    }
