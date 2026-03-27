import json
import logging
import time
from typing import Any, List, Dict
from fastapi import Request

logger = logging.getLogger("resumate")

def parse_json_object(raw: str) -> Dict[str, Any]:
    """Extracted from legacy _parse_json. Cleans markdown fences and extracts first/last { }."""
    if not raw:
        return {}
    cleaned = (raw or "").replace("```json", "").replace("```", "").strip()
    if "{" in cleaned and "}" in cleaned:
        cleaned = cleaned[cleaned.find("{"):cleaned.rfind("}") + 1]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning("JSON PARSE FAILED: %s | Content: %s", e, cleaned[:200])
        return {}

def validate_parsed(parsed: Dict[str, Any], required_keys: List[str]) -> None:
    """Standardized validator for AI-produced dictionaries."""
    if not isinstance(parsed, dict) or not parsed:
        raise ValueError("AI response is not a valid object.")
    missing = [k for k in required_keys if k not in parsed]
    if missing:
        raise ValueError(f"AI response missing required keys: {', '.join(missing)}")

def clamp_score(n: Any, lo: float = 0.0, hi: float = 10.0) -> float:
    """Clamps a numeric score to [lo, hi]. Handles string conversion."""
    try:
        val = float(n)
        return round(max(lo, min(hi, val)), 1)
    except (ValueError, TypeError):
        return lo



def safe_list(data: Any, limit: int = 10) -> List:
    """Ensures input is a list and truncates it."""
    if isinstance(data, list):
        return data[:limit]
    return []

# Timed Mode / Coding Helpers
_TIMED_ALLOWED = {"35", "45"}

def _timed_session_key(problem_id: str) -> str:
    return f"timed_mode_{str(problem_id or '').strip()}"

def _timed_mode_state(request: Request, problem_id: str) -> Dict[str, Any]:
    state = request.session.get(_timed_session_key(problem_id)) or {}
    if not state:
        return {"enabled": False, "duration_min": 0, "remaining_sec": 0, "elapsed_sec": 0, "expired": False, "submitted": False, "job_id": ""}
    duration = int(state.get("duration_min") or 0)
    start_ts = int(state.get("start_ts") or 0)
    now = int(time.time())
    elapsed = max(0, now - start_ts)
    total = max(0, duration * 60)
    remaining = max(0, total - elapsed)
    return {
        "enabled": duration > 0, "duration_min": duration, "remaining_sec": remaining,
        "elapsed_sec": elapsed, "expired": remaining <= 0, "submitted": bool(state.get("submitted")),
        "job_id": str(state.get("job_id") or ""),
    }

def _readiness_from_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    total = int((summary or {}).get("total") or 0)
    accept = float((summary or {}).get("accept_rate") or 0.0)
    speed = float((summary or {}).get("avg_runtime_ms") or 0.0)
    consistency = min(100.0, total * 5.0)
    speed_score = 100.0 if speed <= 120 else max(20.0, 140.0 - (speed / 2.5))
    score = round((accept * 0.5) + (consistency * 0.25) + (speed_score * 0.25), 1)
    return {"score": score, "band": "High" if score >= 75 else ("Medium" if score >= 50 else "Low"), "accept_rate": round(accept, 1), "consistency": round(consistency, 1), "speed_score": round(speed_score, 1)}

def _daily_goal_from_attempts(attempts: list, goal_accepted: int = 1, goal_review: int = 1) -> Dict[str, Any]:
    now = int(time.time())
    today = time.strftime("%Y-%m-%d", time.localtime(now))
    bucket = {"accepted": 0, "review": 0}
    for a in attempts[:60]:
        ts = int(a.get("timestamp") or 0)
        if not ts or time.strftime("%Y-%m-%d", time.localtime(ts)) != today: continue
        if str(a.get("mode") or "") == "submit" and str(a.get("status") or "") == "Accepted": bucket["accepted"] += 1
        if str(a.get("mode") or "") in ("run", "submit", "hint", "interviewer"): bucket["review"] += 1
    return {"accepted_today": int(bucket["accepted"]), "review_today": int(bucket["review"]), "goal_accepted": int(goal_accepted), "goal_review": int(goal_review), "goal_met_today": bucket["accepted"] >= goal_accepted and bucket["review"] >= goal_review}

def validate_password_strength(password: str) -> str:
    if len(password or "") < 8:
        return "Password must be at least 8 characters."
    if not any(c.islower() for c in password):
        return "Password must include a lowercase letter."
    if not any(c.isupper() for c in password):
        return "Password must include an uppercase letter."
    if not any(c.isdigit() for c in password):
        return "Password must include a number."
    return ""
