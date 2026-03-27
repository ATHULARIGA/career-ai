from features.shared import call_ai_with_fallback

def generate_ideal_answer(question: str) -> str:
    prompt = f"Generate a concise ideal answer for: {question}. JSON only: {{\"answer\":\"...\"}}"
    try:
        parsed = call_ai_with_fallback(prompt, "", temperature=0)
        answer = str(parsed.get("answer", "")).strip()
        if answer: return answer
    except Exception: pass
    return "Ideal answer unavailable. Focus on clear structure, core concept, tradeoffs, and measurable impact."
