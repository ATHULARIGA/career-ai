import json

from services.ai.provider import get_openrouter_client

client = get_openrouter_client()


def _parse_json(raw: str) -> dict:
    cleaned = (raw or "").replace("```json", "").replace("```", "").strip()
    if "{" in cleaned and "}" in cleaned:
        cleaned = cleaned[cleaned.find("{"):cleaned.rfind("}") + 1]
    return json.loads(cleaned)


def generate_ideal_answer(question: str) -> str:
    prompt = f"""
You are a senior technical interviewer.
Generate a concise ideal answer for this interview question.
Return JSON only:
{{"answer":"Ideal answer here"}}

Question:
{question}
"""
    models = [
        "meta-llama/llama-3.1-8b-instruct",
        "meta-llama/llama-3.3-70b-instruct",
        "meta-llama/llama-3.2-3b-instruct",
        "deepseek/deepseek-chat",
        "openai/gpt-4o-mini",
    ]

    last_error = None
    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=600,
            )
            parsed = _parse_json(response.choices[0].message.content)
            answer = str(parsed.get("answer", "")).strip()
            if answer:
                return answer
        except Exception as e:
            print(f"IDEAL ANSWER FAILED using {model}: {e}")
            last_error = e

    print(f"IDEAL ANSWER FALLBACK TRIGGERED: {last_error}")
    return "Ideal answer unavailable. Focus on clear structure, core concept, tradeoffs, and measurable impact."
