import json
import re
from features.shared import call_ai_with_fallback

def score_resume_lightweight(text: str, jd_text: str, target_role: str, company_tier: str = "General") -> dict:
    """Lightweight 2-metric prompt intended for comparison grids."""
    system = """You are an Elite Recruiter. Evaluate the Resume against the Job Target.
Return JSON ONLY with EXACTLY this structure:
{
  "score": float, // 0-10 overall alignment fit
  "match_percent": int, // 0-100 requirements match percentage
  "summary": "1 sentence verdict focusing on core alignment"
}
"""
    user_prompt = f"""
    Target Role: {target_role or "Not specified"}
    Company Tier: {company_tier or "General"}
    
    Job Description context:
    {jd_text[:2000] if jd_text.strip() else "Match against average role expectations."}
    
    Resume Text:
    {text[:3500]}
    """

    try:
        parsed = call_ai_with_fallback(system, user_prompt, temperature=0.1, max_tokens=250)
        if isinstance(parsed, dict) and "score" in parsed and "match_percent" in parsed:
            return parsed
        return {"score": 0.0, "match_percent": 0, "summary": "Evaluation parse failure."}
    except Exception as e:
        print(f"Lightweight score FAILED: {e}")
        return {"score": 0.0, "match_percent": 0, "summary": "Evaluation timeout/failure."}
