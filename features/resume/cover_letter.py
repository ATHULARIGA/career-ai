from features.shared import call_ai_with_fallback

def generate_cover_letter(resume_text: str, jd_text: str, report: dict) -> str:
    """Writes a tailored cover letter using EXACTLY the skills and facts in the candidate's Resume."""
    system = """You are a professional hiring manager. Write a tailored, 3-4 paragraph cover letter utilizing EXACTLY the skills and facts in the candidate's Resume. 
    Do not invent non-sourced facts, companies, or dates not listed. 
    Explicitly incorporate keywords bridging the specified Keyword Gaps to fit responsibilities. 
    Structure with [Your Name] placeholders. Keep it concise (under 400 words)."""
    
    verified_skills = list(report.get("scores", {}).keys())
    keyword_gaps = report.get("keyword_gaps", [])
    
    user_prompt = f"""
    Write a cover letter based on the following:
    
    Candidate's Verified Skills: {verified_skills}
    Keyword Gaps to address: {keyword_gaps}
    
    Resume Context:
    {resume_text[:4000]}
    
    Job Description Context:
    {jd_text[:2000]}
    """
    
    try:
        content = call_ai_with_fallback(system, user_prompt, temperature=0.2, max_tokens=610)
        if isinstance(content, str) and len(content.strip()) > 300:
            return content.strip()
        return str(content)
    except Exception as e:
        print(f"Cover Letter FAILED: {e}")
        return "Error generating cover letter. Layout limits exceeded."
