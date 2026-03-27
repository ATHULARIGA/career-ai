from features.shared import call_ai_chat

def generate_resume_rewrite(resume_text: str, report: dict) -> str:
    """Rewrites the entire resume into clean Markdown applying ALL suggestions."""
    system = """You are an Elite Resume Writer. Rewrite the provided resume into clean, structured Markdown format.
Apply ALL of our suggestions (incorporate numbers, improve action verbs, structure clearly).
Headings to include: Summary/Profile, Experience, Education, Skills.

ANTI-HALLUCINATION GROUNDING:
- Use ONLY names, dates, companies, and metrics present in the original resume.
- Do NOT invent new achievements, titles, or technologies.
- Use placeholders like "[X%]" or "[Metric]" ONLY where numbers are suggested for improvement but missing in original text.
"""
    verified_skills = list(report.get("scores", {}).keys())
    suggested_rewrites = report.get("targeted_rewrites", [])
    
    user_prompt = f"""
    Rewrite this resume document incorporating guidance and skills below:
    
    Target Skills and Gaps: {verified_skills}
    Suggested Improvements to use as reference: {suggested_rewrites}
    
    Original Resume Text:
    {resume_text[:4500]}
    """
    
    try:
        content = call_ai_chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=1800,
        )
        cleaned = (content or "").strip()
        if len(cleaned) > 200:
            return cleaned
        return "Could not generate a complete resume rewrite right now. Please try Regenerate."
    except Exception as e:
        print(f"Resume Rewrite FAILED: {e}")
        return "Error generating fixed resume. Capacity limits exceeded."
